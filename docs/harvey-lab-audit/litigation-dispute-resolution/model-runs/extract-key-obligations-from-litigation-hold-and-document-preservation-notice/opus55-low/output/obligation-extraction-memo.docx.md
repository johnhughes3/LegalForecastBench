<!-- Rendered from obligation-extraction-memo.docx for reading; the original file is the deliverable. -->

**PRIVILEGED AND CONFIDENTIAL — ATTORNEY-CLIENT COMMUNICATION / ATTORNEY WORK PRODUCT  
Prepared at the Direction of Counsel in Anticipation of Litigation**

**MEMORANDUM**

|       |                                                                                                                                                                                                   |
|-------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| TO:   | Catherine A. Hargrove / Jonathan D. Prewitt, Hargrove, Tillett & Mays LLP (outside defense counsel)                                                                                               |
| CC:   | Marcus Ellsworth, General Counsel, Ridgeline Therapeutics, Inc. (see Part VIII.G regarding his status as a named custodian)                                                                       |
| FROM: | Legal review team                                                                                                                                                                                 |
| DATE: | March 5, 2025                                                                                                                                                                                     |
| RE:   | Obligation Extraction — DOJ Litigation Hold and Document Preservation Notice, Grand Jury Investigation No. 24-GJ-0387 (issued March 3, 2025), and gap analysis against internal Ridgeline records |

# I. Executive Summary

This memo pulls out every obligation imposed on Ridgeline Therapeutics, Inc. ("Ridgeline") by the March 3, 2025 cover letter and the Litigation Hold and Document Preservation Notice (the "Notice"), including Exhibits A–D. It then checks those obligations against four internal documents: (1) the Records Retention and Destruction Policy, No. RDG-LGL-007 (v2.0, April 15, 2022) (the "Policy"); (2) the January 16, 2025 records destruction confirmation from Patricia Albright (the "Destruction Email"); (3) the March 4/5, 2025 IT migration memo from Dennis Wardlow (the "IT Memo"); and (4) the March 5, 2025 privileged org chart (the "Org Chart").

Our overall assessment: the Notice is broad and it cannot be negotiated on the three hard deadlines. The internal documents show several serious exposures that need action today, before the first deadline:

- **The April 15, 2025 destruction cycle and the 90-day backup tape rotation are still running.** Nothing in the file shows that either has been suspended. Paragraphs 5, 33 and 41 of the Notice required suspension "immediately" on receipt. The tape rotation is also the only possible route to recovering electronic records deleted on January 15, 2025. Tapes holding that data are being overwritten on a rolling basis now, and the last copies will be gone by roughly mid-April 2025.

- **About 4.2 million records were destroyed on January 15, 2025, seven weeks before the Notice.** They fall within Notice categories: KOL event files, Salesforce call records of the regional sales managers and the National Sales Director's team, RPAF correspondence, and 47 boxes of paper at Sentinel. The destruction also appears to have **violated the Policy itself**. Speaker-program event records and RPAF-related records carry a 6-year retention period (Categories L and M), not 3 years. The pre-destruction notice periods were also not followed. Paragraph 46 requires a prompt written disclosure to DOJ.

- **Pre-September 2021 email for several named custodians exists only on six decommissioned Exchange servers at Sentinel Records Management.** These servers have not been powered on or verified since December 2021, and the legacy backup tapes were probably recycled. The IT Memo's count of "8 of 23" affected custodians is **unreliable**. It names two people (Jennifer Calloway and David Yun) who are not on the Notice's custodian list. It also appears not to have checked the seven Exhibit C managers or the two functional-title custodians properly.

- **No Microsoft 365 litigation hold was in place as of the IT Memo.** IT needs Legal's authorization and says it can act within 24–48 hours. Recoverable Items in M365 are purged after 30 days. Teams/Slack messages (1 year), voicemail (90 days) and mobile data (2 years) are all being deleted automatically under Policy settings.

- **Several Notice requirements cannot be met as written, or conflict with Ridgeline's legal position.** Examples: forensic imaging of personal devices belonging to five non-employee HCPs and of employee BYOD devices (the Policy requires consent or a court order); binding RPAF, which is legally independent; and "preserving in current physical condition" servers that must be powered up to be recovered. We recommend raising these with AUSA Faulkner and Trial Attorney Gutierrez in writing now, before the March 13 deadline. The Notice itself (¶51) invites this and warns against unilateral interpretation.

- **The Notice has internal drafting inconsistencies** that affect scope. Examples: 36 categories are referenced but only 34 are listed; the subject-matter area numbering in the body differs from Exhibit B; and ¶47 points to the wrong area for the extended financial-records period. These should be resolved by preserving the broader reading and asking DOJ for written clarification.

# II. Documents Reviewed

| **Document**                                                  | **Date / Author**                                                                                                  | **Relevance**                                                                                                 |
|---------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| DOJ cover letter + Preservation Notice (¶¶1–52, Exhibits A–D) | Mar. 3, 2025; AUSA Brendan K. Faulkner (WDNC) and TA Sonia R. Gutierrez (Fraud Section); FedEx 7749 2103 8856 4410 | Source of all obligations                                                                                     |
| Policy No. RDG-LGL-007 v2.0                                   | Eff. Apr. 15, 2022; approved by Ellsworth, Cho-Rosen, Venkataraman; annual review overdue since Apr. 2023          | Retention periods and routines that must be suspended; internal hold procedures; templates                    |
| Records destruction confirmation email                        | Jan. 16, 2025; P. Albright to D. Cho-Rosen, cc M. Ellsworth, K. Tate                                               | Destruction of ~4.2M records on Jan. 15, 2025; next cycle set for Apr. 15, 2025                               |
| IT migration memo email                                       | Mar. 5, 2025 04:47 UTC (evening of Mar. 4 ET); D. Wardlow to M. Ellsworth, cc D. Cho-Rosen                         | Ashford migration failure; 340,000 un-migrated emails; legacy servers at Sentinel; backup tape status unknown |
| Corporate org chart and entity structure (privileged)         | Mar. 5, 2025; Office of the General Counsel for HTM                                                                | Reporting lines; RPAF independence; vendors; Linden & Pruitt conflict                                         |

# III. Deadline Calendar

The Notice counts every deadline from "receipt." Delivery was by FedEx overnight, so receipt was probably March 4, 2025. However, both the cover letter and the Notice state calendar dates counted from March 3, the mailing date. Paragraph 52 makes the Notice effective on mailing (March 3), while ¶1 says "upon receipt." **We recommend treating the stated calendar dates as binding.** The deadlines are described as "firm and non-negotiable absent written agreement." Please confirm the actual FedEx delivery date for the file.

| **Date**                          | **Obligation**                                                                                                                                                                            | **Source**                       | **Status per file**                                                                                                                              |
|-----------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| Mar. 3, 2025 (Mon.) — immediately | Preservation duty attaches. Suspend all auto-deletion, destruction schedules, backup tape recycling, email purges and vault clean-up                                                      | Cover letter; ¶¶1, 5, 33, 41, 52 | **CRITICAL — no evidence of suspension.** M365 holds not yet authorized; tape rotation and Apr. 15 cycle still scheduled                         |
| Mar. 13, 2025 (Thu.)              | Issue written preservation notices to all third-party vendors (at least Veeva, SAP, Concur, IntegriCall) instructing them to suspend deletion; then obtain written confirmation from each | Cover letter (i); ¶43; ¶45(c)    | Not started. Recommend adding Sentinel, Salesforce, Microsoft, Slack, Ashford, Linden & Pruitt, and the Atlanta/other off-site storage operators |
| Mar. 17, 2025 (Mon.)              | Written certification to Faulkner and Gutierrez covering items (a)–(f) of ¶45 (see Part V.K)                                                                                              | Cover letter (ii); ¶45; Exh. C   | Not started. Needs individual hold notices, custodian acknowledgments, named oversight person and point of contact                               |
| Mar. 24, 2025 (Mon.)              | Complete forensic (full physical, not logical) imaging of all personal and company mobile devices of all 23 named custodians, with a chain-of-custody log                                 | Cover letter (iii); ¶¶17, 40     | Not started. Includes 5 non-employee HCPs and BYOD devices; see Part VIII.E                                                                      |
| Promptly / ongoing                | Written notice to DOJ of any data loss or destruction, whether before or after the Notice, including type, volume, dates and remediation                                                  | ¶46                              | Triggered already by the Jan. 15 destruction and the 2021 migration gap                                                                          |
| Quarterly (internal)              | Hold reminders to custodians                                                                                                                                                              | Policy §6.3                      | Put on calendar                                                                                                                                  |
| Apr. 15, 2025                     | Next Policy destruction cycle, and approximate date the last backup tapes holding Jan. 15-deleted data will be overwritten (90 days)                                                      | Destruction Email; Policy §4.3   | **CRITICAL — cancel the cycle and pull the tapes now**                                                                                           |
| Until DOJ lifts in writing        | All obligations continue, including for newly created material                                                                                                                            | ¶¶5, 32, 33, 52; Exh. A          |                                                                                                                                                  |

# IV. Scope Parameters

## A. Covered Entities and Persons

- Ridgeline Therapeutics, Inc. (Delaware; NASDAQ: RDGT) and all subsidiaries, affiliates, divisions and related entities. The Notice expressly includes **RPAF** (¶4). It binds all officers, directors, employees, agents and representatives "wherever situated" (¶1). That covers the 14 domestic offices and the 3 international sites (London, Munich, Tokyo per Policy §1.2).

- Specific facilities: Durham headquarters (4200 Meridian Crossings Blvd, Ste. 1100) and the Atlanta field office (770 Peachtree Industrial Blvd, Ste. 300) (¶¶6, 44). Also the Exhibit C offices in Philadelphia, Dallas, Chicago, Seattle and Denver, and the Sentinel Records Management facility in Raleigh, NC (Account SM-2247891) (¶¶41–42).

## B. Subject Matter

- \(1\) KOL Program / speaker bureau (~\$147.3M spend, ~14,800 events, 2019–2024); (2) RPAF (~\$89.6M in grants to ~22,400 Velcara patients); (3) marketing, promotion and sale of Velcara (ridgenostat) (cover letter; ¶¶2, 7–9).

- Statutes: Anti-Kickback Statute (42 U.S.C. §1320a-7b(b)), False Claims Act (31 U.S.C. §§3729–3733), wire fraud (18 U.S.C. §1343), conspiracy (18 U.S.C. §371) (¶10). Note that the cover letter and ¶2 mention only the AKS and FCA. ¶10 adds §§1343 and 371, which suggests individual criminal exposure. Obstruction under 18 U.S.C. §1519 is the stated enforcement threat (¶¶2, 34, 49).

- **Related compounds (¶31):** the Notice extends to "ridgenostat and all related compounds" to the extent they relate to the investigation, and must be construed broadly. The Org Chart identifies four pipeline oncology compounds. Their R&D, medical affairs and HCP-consulting files should be assessed and, when in doubt, preserved.

## C. Time Periods

| **Period**                      | **Applies to**                                                                                   | **Source**                | **Note**                                                                                                                                    |
|---------------------------------|--------------------------------------------------------------------------------------------------|---------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| Jan. 1, 2019 – Mar. 3, 2025     | General Relevant Period                                                                          | ¶12; Exh. A               | "Unless otherwise specified"                                                                                                                |
| After Mar. 3, 2025 (continuing) | Newly created or received material                                                               | ¶32; Exh. A               | ¶32 refers only to "Documents, Records, or Materials"; Exh. A adds Communications and ESI. Apply the broader reading                        |
| Jan. 1, 2017 – present          | Financial records, accounting entries, GL, budgets and payment records for KOL, RPAF and Velcara | ¶47                       | Includes archival and backup copies of 2017–2018 financial data. See risk in Part VIII.H                                                    |
| Pre-2019 (no end date)          | Some custodians (Exh. C start dates from 2015) and pre-launch activity                           | ¶19 (non-exhaustive); ¶31 | Not expressly required. Consider preserving pre-2019 KOL restructuring documents (Exh. A says the current KOL structure dates from Q1 2019) |

## D. Defined Terms — Hierarchy and Drafting Traps

The Notice defines a nested hierarchy: **Documents** ⊂ **Records** (adds structured data in ERP, CRM and other systems) ⊂ **Materials** (adds physical objects, samples, promotional items and branded merchandise) (¶3(a)–(c)). **Communications** (¶3(d)) and **ESI** (¶3(e)) are defined separately. ESI includes metadata, forensically recoverable deleted files, logs and backups. Communications include social-media DMs, and oral conversations to the extent they were memorialized. **HCP** (¶3(g)) extends to pharmacists and RNs.

The operative paragraphs use these terms inconsistently. For example: ¶¶21, 22 and 26 cover "Documents, Records, and Communications" but not Materials; ¶¶19, 23, 24, 27 and 28 use undefined lower-case terms; ¶30 uses the undefined term "Documentation"; ¶32 omits Communications and ESI. **Recommendation:** read every paragraph as covering all five defined terms. Do not rely on any narrower reading without written DOJ agreement. ¶¶19, 31 and 51 support this approach.

## E. Named Custodians (23)

Paragraph 16 counts 23 custodians: 9 executives (¶13) + 7 regional sales managers (Exh. C) + 2 functional-title employees + 5 external HCPs (Exh. D). The "IT Memo gap" column reflects whether the IT Memo reports pre-September 2021 email as un-migrated. This must be re-verified; see Part VIII.C.

| **\#** | **Custodian**           | **Role / Detail**                                               | **Source**        | **IT Memo gap / notes**                                                                              |
|--------|-------------------------|-----------------------------------------------------------------|-------------------|------------------------------------------------------------------------------------------------------|
| 1      | Dr. Priya Venkataraman  | CEO                                                             | Exec (¶13)        | Not listed                                                                                           |
| 2      | Marcus Ellsworth        | General Counsel                                                 | Exec (¶13)        | Not listed. Also the addressee and hold owner; see VIII.G                                            |
| 3      | Diane Cho-Rosen         | Chief Compliance Officer                                        | Exec (¶13)        | Not listed. Oversees IntegriCall and Records Management                                              |
| 4      | Dr. Franklin Osei       | VP Medical Affairs                                              | Exec (¶13)        | **Affected.** Linden & Pruitt contact; see VIII.F                                                    |
| 5      | Gregory Hsu             | VP Commercial Operations                                        | Exec (¶13)        | **Affected**                                                                                         |
| 6      | Amanda Terrell          | Sr. Dir., Speaker Programs                                      | Exec (¶13)        | **Affected**                                                                                         |
| 7      | Richard Blaine          | Dir., Patient Assistance Programs                               | Exec (¶13)        | **Affected.** RPAF liaison                                                                           |
| 8      | Dr. Katerina Novak      | MSL, Southeast (Atlanta)                                        | Exec (¶13)        | **Affected**                                                                                         |
| 9      | Luis Delgado            | National Sales Director                                         | Exec (¶13)        | **Affected.** His team's call records destroyed Jan. 15                                              |
| 10     | Tonya M. Bradshaw       | RSM Mid-Atlantic (Durham); start 3/12/2017                      | Exh. C            | Not listed. IT Memo instead names "Jennifer Calloway, RSM Mid-Atlantic"                              |
| 11     | Kevin J. Fontaine       | RSM Southeast (Atlanta); start 6/5/2016                         | Exh. C            | Not listed                                                                                           |
| 12     | Sarah E. Lindgren       | RSM Northeast (Philadelphia); start 1/8/2018                    | Exh. C            | Not listed                                                                                           |
| 13     | David R. Castillo       | RSM Southwest (Dallas); start 9/15/2015                         | Exh. C            | Not listed                                                                                           |
| 14     | Michelle A. Thornton    | RSM Midwest (Chicago); start 11/2/2017                          | Exh. C            | Not listed                                                                                           |
| 15     | James W. Okafor         | RSM Pacific NW (Seattle); start 4/22/2019                       | Exh. C            | Not listed. IT Memo instead names "David Yun, RSM West Coast"; no West Coast region exists in Exh. C |
| 16     | Christine L. Sperling   | RSM Mountain West (Denver); start 8/14/2018                     | Exh. C            | Not listed                                                                                           |
| 17     | \[To be identified\]    | Director of Pricing Analytics (current incumbent)               | ¶16(c)(i)         | Unknown. Identify by name; also identify prior incumbents during the Relevant Period                 |
| 18     | \[To be identified\]    | Assoc. Dir., Government Accounts (current incumbent)            | ¶16(c)(ii)        | Unknown. Same as above                                                                               |
| 19     | Dr. Raymond T. Whitford | Oncology, Calder Medical Center, Charlotte; \$2.3M / 412 events | Exh. D (external) | N/A. Ridgeline-side communications only                                                              |
| 20     | Dr. Ingrid M. Svensson  | Heme/Onc, Pinnacle Health, Atlanta; \$1.9M / 347                | Exh. D (external) | N/A                                                                                                  |
| 21     | Dr. Oscar L. Famuyide   | Med Onc, Lakeridge Univ. Hosp., Raleigh; \$1.6M / 289           | Exh. D (external) | N/A                                                                                                  |
| 22     | Dr. Hannah J. Prescott  | Onc Pharmacy, Briarwood Cancer Inst., Nashville; \$1.4M / 254   | Exh. D (external) | N/A                                                                                                  |
| 23     | Dr. Samuel K. Anand     | Pulm Onc, Meridian Valley MC, Richmond; \$1.2M / 218            | Exh. D (external) | N/A                                                                                                  |

**Other people to add to the hold list (not named in the Notice, but in scope).** These should get Ridgeline hold notices; DOJ may supplement the list under ¶18.

- Jennifer Calloway and David Yun, named in the IT Memo. They may be former or re-titled RSMs whose data sits on the legacy servers.

- Employees with the most frequent contact with each Exhibit D HCP. ¶24 requires preservation instructions to these people. Identify them from Veeva/Salesforce call data, Concur and email metadata.

- The three RPAF directors who are Ridgeline officers or designees (Org Chart §4).

- Dennis Wardlow and Brian Kepler (IT); Patricia Albright and Kevin Tate (Records Management); the CFO's office (the decision to defer the migration fix); and Ashford project personnel.

- Promotional/MLR review committee members, Finance and the Controller (¶47), and Linden & Pruitt engagement contacts.

# V. Obligation Extraction Matrix

Each obligation is listed with its source, deadline, recommended owner and current status. "HTM" = Hargrove, Tillett & Mays. "Greenwell" = Greenwell Analytics Group (forensic vendor, engaged by HTM).

## A. General Preservation and Suspension

| **Ref** | **Obligation**                                                                                                                                                                                                                 | **Source**  | **Deadline**               | **Owner**            | **Status / gap**                                                                                                                    |
|---------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|----------------------------|----------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| A1      | Preserve all Documents, Records, Materials, Communications and ESI that are or may be relevant; the categories are non-exhaustive                                                                                              | ¶¶5, 19, 33 | Immediate / continuing     | GC + HTM             | Hold notice not yet issued                                                                                                          |
| A2      | The Notice overrides Policy RDG-LGL-007 and any successor policy; suspend all destruction schedules, auto-deletion, tape recycling, email purges and vault clean-up, whether automated or manual, company-wide or departmental | ¶¶5, 33     | Immediate                  | GC; IT; Records Mgmt | **CRITICAL — Apr. 15 cycle still scheduled.** Platform retention settings (M365, Slack, Teams, Veeva, Salesforce, MDM) still active |
| A3      | No destruction, deletion, shredding, erasure, overwriting or demagnetizing of in-scope material                                                                                                                                | ¶33         | Continuing                 | All                  | Notify facilities/shredding vendors; lock shred bins at Durham and Atlanta                                                          |
| A4      | Construe scope broadly and err toward preservation (related compounds and relevance)                                                                                                                                           | ¶31         | Continuing                 | HTM                  | Adopt as written protocol                                                                                                           |
| A5      | Continuing duty for material created after Mar. 3, 2025                                                                                                                                                                        | ¶32; Exh. A | Until lifted in writing    | GC                   | Holds must be prospective (M365 holds do this; retention policy changes are also needed)                                            |
| A6      | Preserve potentially privileged material; no destruction on privilege grounds; keep a privilege log for any withheld production                                                                                                | ¶¶29, 48    | Continuing / at production | HTM                  | See L&P issue, VIII.F                                                                                                               |

## B. Custodian Obligations

| **Ref** | **Obligation**                                                                                                                                                               | **Source**       | **Deadline**   | **Owner**            | **Status / gap**                                                                    |
|---------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------|----------------|----------------------|-------------------------------------------------------------------------------------|
| B1      | Preserve all data of all 23 custodians on corporate systems, personal devices, personal webmail, personal cloud (Dropbox, Google Drive, iCloud, OneDrive) and home computers | ¶¶13–17          | Immediate      | GC / HTM             | Individual hold notices and personal-account questionnaires needed                  |
| B2      | Give each Exhibit C RSM a copy of the Notice or a hold notice; confirm receipt and acknowledgment in the ¶45 certification                                                   | Exh. C           | By Mar. 17     | GC / HTM             | Use Policy App. B template, updated (it wrongly lists L&P-era contacts; see VIII.F) |
| B3      | Identify the 2 functional-title custodians                                                                                                                                   | ¶16(c)           | Before Mar. 17 | HR / GC              | Not done. Org Chart omits them entirely                                             |
| B4      | Preserve all communications with, and all contracts, payments, 1099s, expenses and travel records for, the Exhibit D HCPs; instruct the employees with most frequent contact | ¶¶15, 24; Exh. D | Immediate      | Commercial Ops / HTM | Frequent-contact employees must be identified                                       |
| B5      | Accept and implement any DOJ supplement to the custodian list                                                                                                                | ¶18              | On notice      | GC / HTM             | Build a tracking process                                                            |

## C. Subject-Matter Categories (Exhibit B Cats. 1–34, plus body ¶¶20–30)

| **Ref** | **Obligation**                                                                                                                                                                                                  | **Source**       | **Deadline** | **Owner**                    | **Status / gap**                                                                                                                         |
|---------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------|--------------|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| C1      | Area 1 — KOL administration: contracts; training/slide decks; event planning, venue, catering, AV, travel, attendee lists; post-event reports; SOPs; HCP correspondence (Cats. 1–6)                             | ¶20; Exh. B      | Immediate    | Terrell / Hsu                | **Jan. 15 destruction took ~380,000 2019–2021 event files (Cats. 3–4)**                                                                  |
| C2      | Area 2 — Compensation and FMV: FMV and benchmarking; payment records, 1099s; approvals and committee minutes; rate communications (Cats. 7–10)                                                                  | ¶21; Exh. B      | Immediate    | Finance / Terrell            | Destruction Email says these were excluded (7-year retention). Verify                                                                    |
| C3      | Area 3 — HCP selection and due diligence: criteria, rubrics, rankings; credentialing, COI; OIG LEIE / SAM screening; frequency and concentration analyses (Cats. 11–14)                                         | ¶22; Exh. B      | Immediate    | Compliance / Terrell         | Said to be excluded from destruction. Verify                                                                                             |
| C4      | Area 4 (body only) — all HCP communications about Velcara, with any HCP, in any context (efficacy, safety, dosing, formulary, prescribing, reimbursement)                                                       | ¶23              | Immediate    | Commercial / Medical Affairs | Very broad: effectively all field and MSL communications. **No matching Exhibit B category.** Call records were partly destroyed Jan. 15 |
| C5      | Area 4B — communications with the Exhibit D HCPs on every channel (email, SMS, Slack, Teams, voicemail, third-party apps, employees' personal devices)                                                          | ¶24              | Immediate    | HTM / IT                     | Voicemail on 90-day and IM on 1-year deletion. Suspend                                                                                   |
| C6      | RPAF: governing documents; board minutes; grant applications and disbursements; Ridgeline–RPAF communications; RPAF financials and Forms 990 (Cats. 15–19)                                                      | ¶25; Exh. B      | Immediate    | Blaine / GC / RPAF board     | **~320,000 RPAF correspondence records destroyed Jan. 15.** RPAF not yet notified; see VIII.D                                            |
| C7      | Compliance: internal audits; compliance reports (including for the CCO); third-party audits; IntegriCall hotline records; internal investigation files (Cats. 20–23)                                            | ¶26; Exh. B      | Immediate    | Cho-Rosen                    | IntegriCall retains 6 years under its addendum. Suspend                                                                                  |
| C8      | Financial: GL, journals, reconciliations; AP/AR; budgets and forecasts; Velcara revenue by region, territory, rep and payer (Cats. 24–27), **from Jan. 1, 2017**                                                | ¶¶27, 47; Exh. B | Immediate    | CFO / Controller             | 2017–2018 data at risk under the 7-year schedule (Policy Cat. D)                                                                         |
| C9      | Marketing: sales aids, reprints, promotional items, branded merchandise (physical Materials); PRC/MLR minutes and approvals; digital, social, web, search and email campaigns (Cats. 28–30)                     | ¶28; Exh. B      | Immediate    | Marketing / MLR              | Policy Cat. G 5-years-from-last-use. Suspend. Secure physical samples and merchandise                                                    |
| C10     | Government inquiry: all communications about any DOJ, HHS-OIG, FDA, state AG or other inquiry; outside counsel communications including **Linden & Pruitt** (Cats. 31–32)                                       | ¶29; Exh. B      | Immediate    | GC / HTM                     | Also covers lobbyist and government affairs communications (Cat. 32)                                                                     |
| C11     | IT documentation: architecture, data maps, access controls, retention and purge configurations, **all migration and decommissioning documentation** including the 2021 on-prem-to-cloud migration (Cats. 33–34) | ¶30; Exh. B      | Immediate    | Wardlow                      | Wardlow reports Ashford agreement, incident report, \$280K proposal, budget memos and Sentinel inventory preserved. Collect them to HTM  |

## D. ESI Format and Email

| **Ref** | **Obligation**                                                                                                                                                                                                                                     | **Source** | **Deadline** | **Owner**      | **Status / gap**                                                                                                                        |
|---------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|--------------|----------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| D1      | Preserve all ESI natively with metadata intact. No printing, PDF, CSV export or screenshots as a substitute. Keep all versions and locations. No action that alters metadata                                                                       | ¶35        | Immediate    | IT / Greenwell | Warn custodians against "self-collection" (forwarding and moving files changes metadata)                                                |
| D2      | Email of all 23 custodians: sent, received, drafts, deleted, archived; Exchange and M365 and any platform used in the Relevant Period; Recoverable Items/Purges must not be purged; archive and journal mailboxes kept; personal webmail preserved | ¶36        | Immediate    | IT             | **CRITICAL — M365 holds not in place.** 30-day Recoverable Items purge (Policy §4.1) still running. Legacy Exchange covered; see VIII.C |

## E. Messaging, Enterprise Apps, Cloud

| **Ref** | **Obligation**                                                                                                                                        | **Source** | **Deadline** | **Owner**            | **Status / gap**                                                                                                                                                        |
|---------|-------------------------------------------------------------------------------------------------------------------------------------------------------|------------|--------------|----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| E1      | Preserve Slack (all channels, DMs, threads) and Teams (chats, channels, meeting chats, recordings). Set retention to **indefinite**. No auto-deletion | ¶37        | Immediate    | IT                   | Policy Cat. T 1-year deletion; Slack project-channel archiving after 90 days; Stream recordings 1 year. Change settings on the Enterprise Grid org and the Teams tenant |
| E2      | Preserve Salesforce CRM, Veeva Vault/CRM, SAP ERP and Concur in full, including audit trails. No deletion, archiving or loss of access                | ¶38        | Immediate    | IT / business owners | Policy Cat. F 2-year purge configured in Veeva/Salesforce (§4.4). Disable it. Confirm whether Salesforce source data survives behind the destroyed "exports"            |
| E3      | SharePoint (online and on-prem) and OneDrive: keep full version histories; no version-limit reduction; suspend disposition rules                      | ¶39        | Immediate    | IT                   | Apply M365 retention holds; check version-limit settings                                                                                                                |

## F. Mobile Devices

| **Ref** | **Obligation**                                                                                                                                                                                                             | **Source**        | **Deadline** | **Owner**       | **Status / gap**                                                                             |
|---------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|--------------|-----------------|----------------------------------------------------------------------------------------------|
| F1      | Full physical forensic image (bit-for-bit; deleted data, app data, iMessage, WhatsApp, Signal, Telegram, location, browser) of **all personal and company devices of all 23 custodians**; logical extraction is not enough | ¶¶17, 40          | **Mar. 24**  | HTM / Greenwell | Includes 5 external HCPs and BYOD. Policy §4.5 requires consent or a court order; see VIII.E |
| F2      | Use a qualified examiner and industry tools (Cellebrite UFED, GrayKey, Magnet AXIOM)                                                                                                                                       | ¶40               | Mar. 24      | Greenwell       | Confirm capacity: roughly 18 employees × 1–3 devices in 7+ cities                            |
| F3      | Chain-of-custody log per device: date, time, make/model, serial/IMEI, custodian, examiner                                                                                                                                  | ¶40               | Per device   | Greenwell       | Template needed                                                                              |
| F4      | Meanwhile: stop MDM remote wipes, device refreshes and trade-ins; suspend the 2-year mobile retention (Policy Cat. V); instruct custodians not to delete messages or disable auto-delete settings                          | ¶¶5, 33 (implied) | Immediate    | IT              | Check disappearing-message settings (Signal, WhatsApp, iMessage "keep messages 30 days")     |

## G. Backup Tapes, Legacy Hardware, Paper

| **Ref** | **Obligation**                                                                                                                                                                                                                                                | **Source** | **Deadline** | **Owner**                 | **Status / gap**                                                                                                                                                   |
|---------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|--------------|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| G1      | Suspend the 90-day backup rotation **in its entirety**; no tape recycled, overwritten or degaussed; covers tapes offsite at Sentinel and any DR vendor; notify those vendors                                                                                  | ¶41        | Immediate    | IT / GC                   | **CRITICAL.** Tapes are stored at Sentinel (Policy §4.3). They may hold the only copies of data deleted Jan. 15, 2025                                              |
| G2      | Preserve decommissioned servers, drives, arrays, NAS and tape libraries in current physical condition; no disposal without written DOJ authorization; keep storage contracts; notify the facility operator in writing; keep retired legacy systems accessible | ¶42        | Immediate    | IT / GC                   | Six Dell PowerEdge Exchange servers at Sentinel (SM-2247891). Pay invoices; written hold to Sentinel. Tension with recovery; see VIII.C                            |
| G3      | Paper: secure and restrict access to custodian offices and central files at Durham and Atlanta; no removal (except safeguarded business use), shredding or discard; inventory off-site paper storage and instruct operators                                   | ¶44        | Immediate    | Facilities / Records Mgmt | 47 Sentinel boxes (2019–2020) destroyed Jan. 15 (Cert. SM-CERT-2025-00412). Inventory the remaining Sentinel boxes. Extend to other Exh. C offices as a precaution |

## H. Third-Party Notices

| **Ref** | **Obligation**                                                                                                                                                                                                                 | **Source** | **Deadline**             | **Owner** | **Status / gap**                                                                         |
|---------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|--------------------------|-----------|------------------------------------------------------------------------------------------|
| H1      | Written preservation notices to all vendors hosting in-scope data, at least Veeva, SAP SE, Concur and IntegriCall, instructing them to suspend deletion, purging and disposal and preserve Ridgeline data in its current state | ¶43        | **Mar. 13**              | GC / HTM  | Use Policy App. C template (5-business-day confirmation). Full recipient list in Part IX |
| H2      | Obtain written confirmation of implementation from each vendor                                                                                                                                                                 | ¶43        | ASAP; ideally by Mar. 17 | GC        | Track in a log                                                                           |
| H3      | Provide copies of the vendor notices to DOJ on request                                                                                                                                                                         | ¶43        | On request               | HTM       | Keep a clean set                                                                         |

## I–J. Reporting, Cooperation, Modification

| **Ref** | **Obligation**                                                                                                                                                                                                                          | **Source**        | **Deadline** | **Owner**   | **Status / gap**                                                                                                                   |
|---------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|--------------|-------------|------------------------------------------------------------------------------------------------------------------------------------|
| I1      | Prompt written notice to DOJ of any circumstance preventing compliance, including pre-Notice destruction, data loss, system failures and vendor contract expiry, with a detailed description, types and volumes, dates, and remediation | ¶46               | Promptly     | HTM         | **Triggered:** Jan. 15 destruction; migration gap; possible recycled legacy tapes; Recoverable Items/IM loss after Mar. 3 (if any) |
| I2      | Direct all communications about the Notice exclusively to AUSA Faulkner ((704) 338-3170) and TA Gutierrez ((202) 514-7023)                                                                                                              | Cover letter; ¶51 | Continuing   | HTM         | Route through HTM                                                                                                                  |
| I3      | Raise scope questions promptly rather than interpreting unilaterally; deadlines may be changed only by written agreement                                                                                                                | Cover letter; ¶51 | Now          | HTM         | See Part XI                                                                                                                        |
| J1      | Cooperation is expected and weighs in charging and sentencing decisions; non-cooperation is an aggravating factor                                                                                                                       | ¶50               | Continuing   | HTM / Board | Supports early, transparent disclosure                                                                                             |

## K. The March 17 Compliance Certification (¶45) — Required Contents

| **Item** | **Must confirm**                                                                                                                                               | **Readiness**                                                                                       |
|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| \(a\)    | Company-wide hold implemented, including individual notices to all named custodians and to all departments, divisions and business units holding relevant data | Not ready. Needs notices, acknowledgments (Exh. C) and the 2 functional-title custodians identified |
| \(b\)    | All auto-deletion, destruction, tape recycling, email purge and disposal routines suspended company-wide                                                       | Not ready. See A2, D2, E1–E3, G1                                                                    |
| \(c\)    | Written preservation notices issued to the vendors in ¶43                                                                                                      | Not ready. Due Mar. 13                                                                              |
| \(d\)    | Steps initiated to image mobile devices (personal and company) of all 23 custodians, with a projected completion timeline                                      | Not ready. Needs Greenwell schedule and a position on HCP and BYOD devices                          |
| \(e\)    | Name and title of the person(s) responsible for overseeing compliance                                                                                          | Decision needed. We recommend HTM plus a non-custodian Ridgeline officer; see VIII.G                |
| \(f\)    | Point of contact: name, title, address, phone, email                                                                                                           | Recommend HTM (Hargrove/Prewitt)                                                                    |

**Caution:** the certification must be accurate and properly qualified. A false or overstated certification could itself create §1519/§1001 exposure. It should be read together with (or come after) the ¶46 disclosure of known losses, and should not certify facts that have not been verified, such as the status of the backup tapes.

# VI. Reconciling the Notice's Category Numbering

The body of the Notice and Exhibit B number the subject-matter areas differently. Paragraph 19 refers to "thirty-six (36) categories" in nine areas, but Exhibit B lists only 34.

| **Topic**                             | **Body ¶ and area \#**           | **Exhibit B area \#** | **Categories**                                            |
|---------------------------------------|----------------------------------|-----------------------|-----------------------------------------------------------|
| Speaker program administration        | ¶20 — Area 1                     | Area 1                | 1–6                                                       |
| Compensation / FMV                    | ¶21 — Area 2                     | Area 2                | 7–10                                                      |
| HCP selection / due diligence         | ¶22 — Area 3                     | Area 3                | 11–14                                                     |
| HCP communications (broad and Exh. D) | ¶¶23–24 — Area 4 (Parts A and B) | **None**              | Unnumbered. Probably the 2 "missing" categories (36 − 34) |
| Patient assistance / RPAF             | ¶25 — Area 5                     | Area 4                | 15–19                                                     |
| Compliance / audit                    | ¶26 — Area 6                     | Area 5                | 20–23                                                     |
| Financial records                     | ¶27 — Area 7                     | Area 6                | 24–27                                                     |
| Marketing / promotional               | ¶28 — Area 8                     | Area 7                | 28–30                                                     |
| Government inquiry communications     | ¶29 — Area 9 Part A              | Area 8                | 31–32                                                     |
| IT / data systems                     | ¶30 — Area 9 Part B              | Area 9                | 33–34                                                     |

**Consequence for ¶47:** the extended 2017 period applies to "Subject-Matter Area 7 (Categories 24–27) of Exhibit B." In Exhibit B, Area 7 is Marketing (Categories 28–30); Categories 24–27 are Financial, which is Area 6. The text of ¶47 and the category numbers show that financial records are intended. **Recommendation:** apply the 2017 start date to Categories 24–27 and all financial and payment records. Also consider preserving 2017–2018 Velcara pre-launch marketing materials (Area 7 in Exhibit B) until DOJ clarifies in writing.

# VII. Conflicts Between the Notice and Internal Policy / Practice

| **Policy RDG-LGL-007 provision**                                                               | **Notice requirement**                                                        | **Required action**                                                                                                                               |
|------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| §5.1 quarterly destruction (Jan/Apr/Jul/Oct 15); next cycle Apr. 15, 2025                      | ¶¶5, 33: all destruction suspended                                            | Cancel the Apr. 15 cycle in writing; instruct the Records Coordinator; direct Sentinel to take no destruction orders without HTM countersignature |
| §4.3 90-day tape rotation; no permanent archive                                                | ¶41: suspend rotation entirely                                                | Pull all tapes from rotation now; buy new media for DR; label with a hold reference                                                               |
| §4.1 30-day Recoverable Items purge; Cat. E 3-year email retention                             | ¶36: no purge of Recoverable Items or Purges; archives and journals preserved | Org-wide M365 retention hold (not only 23 mailboxes, given ¶23 breadth); Litigation Hold on custodian mailboxes                                   |
| Cat. T IM 1 year; Slack 90-day archiving; Teams recordings 1 year                              | ¶37: indefinite retention                                                     | Change Slack Enterprise Grid and Teams retention to indefinite, org-wide                                                                          |
| Cat. U voicemail 90 days                                                                       | ¶¶3(d), 24: voicemail is a Communication                                      | Suspend voicemail purge (phone system / Teams Voice)                                                                                              |
| Cat. V mobile data 2 years; §4.5 MDM remote wipe                                               | ¶40: full forensic images                                                     | Suspend wipes and device replacement; image devices                                                                                               |
| §4.5 BYOD: imaging requires employee consent or court order                                    | ¶¶17, 40: image personal devices                                              | Obtain written consent; escalate refusals to HTM; tell DOJ; possible separate counsel for individuals                                             |
| Cat. F 2-year CRM retention (Veeva, Salesforce)                                                | ¶38: preserve CRM in full, including audit trail                              | Disable purge jobs; vendor notices                                                                                                                |
| Cat. G 5 years from last use; K, L, M 6 years; D 7 years                                       | ¶¶5, 47: all suspended; financial records back to 2017                        | Suspend all schedules; confirm 2017–2018 financial data still exists                                                                              |
| §1.2 / §3.3: RPAF outside Policy                                                               | ¶4: RPAF expressly bound                                                      | Separate notice to RPAF board and executive director; see VIII.D                                                                                  |
| §2.1 lists Linden & Pruitt as "current" regulatory counsel; App. B/C templates dated Apr. 2022 | ¶29: preserve L&P communications                                              | Update templates; route hold questions to HTM, not L&P                                                                                            |
| §7.2 decommissioned hardware may be destroyed with VP-IT + GC dual approval                    | ¶42: no disposal without written DOJ authorization                            | Freeze all disposition; notify Sentinel that no approval is valid without DOJ authorization                                                       |
| §5.3 Certificate of Destruction requires a "no hold in effect" statement                       | ¶46: disclosure of pre-Notice destruction                                     | Collect all certificates and deletion logs (they are themselves in scope: Cats. 33–34)                                                            |

# VIII. Key Risk Issues and Gap Analysis

## A. The January 15, 2025 Destruction Cycle

**Facts (Destruction Email).** On January 15, 2025, Records Management destroyed about 4.2 million records dated 2019–2021 (call records to 2022):

| **Tranche**                                                                                                                                                                           | **Volume** | **Notice categories implicated**                         | **Retention period cited vs. the actual Policy**                                                                                                                                                                                             |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|----------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Routine business correspondence (emails and attachments, Jan. 2019–Dec. 2021)                                                                                                         | ~2.1M      | Potentially all; ¶23 HCP communications; custodian email | 3 yrs "per §4.2". The Policy's schedule is in §3.2 (Cat. E); §4.2 covers IM. Substantive speaker, RPAF or compliance emails carry 6–7 year periods (§3.1: longest applies)                                                                   |
| Sales call records and field activity reports (Salesforce exports, ride-along notes, territory summaries, Jan. 2019–Dec. 2022), including RSMs and the National Sales Director's team | ~1.4M      | ¶23; Cats. 14, 27; Exh. C custodians; Delgado            | 2 yrs "per §4.5" (actually Cat. F; §4.5 covers mobile devices)                                                                                                                                                                               |
| KOL event files: attendance logs, planning documents, venue contracts, post-event summaries (2019–2021)                                                                               | ~380K      | Cats. 1, 3, 4 (direct hit)                               | 3 yrs "per §4.8". **The Policy has no §4.8. Cat. L and §8.2 require 6 years** for "event documentation (including event planning records, venue contracts…), attendee lists." These records were apparently not yet eligible for destruction |
| RPAF routine correspondence (2019–2021)                                                                                                                                               | ~320K      | Cat. 18; ¶25                                             | 3 yrs "per §4.2". **Cat. M and §8.3 require 6 years** for Ridgeline–RPAF interaction records and patient correspondence on Ridgeline systems                                                                                                 |
| Paper: 47 boxes at Sentinel (2019–2020) plus on-site shredding at Durham                                                                                                              | —          | ¶44; unknown contents                                    | Cert. SM-CERT-2025-00412; box index needed                                                                                                                                                                                                   |

**Additional procedural defects compared with Policy §5.1:** department heads were notified on January 6 with a 7-day objection window. The Policy requires 30 days' notice and a 15-day response window. The Destruction Email also cites the wrong Policy sections for every retention period. The GC's office gave the "no active holds" confirmation on January 13.

**Why this matters.** The destruction happened before the Notice, and the Notice alone does not make it unlawful. But: (i) the grand jury number (24-GJ-) indicates a 2024 investigation. Under Policy §6.1, the duty to preserve arises on "reasonable notice," which includes whistleblower or hotline reports, qui tam activity, subpoenas to third parties such as the Exhibit D HCPs, or industry enforcement trends. (ii) Destroying records that the company's own Policy required it to keep weakens any "routine, good-faith destruction" defense. (iii) The records go to the core of the investigation (KOL events, field call records of named custodians, RPAF communications). (iv) Paragraph 46 expressly requires disclosure of pre-Notice destruction.

**Actions:**

- Stop the tape rotation today. Electronic deletions from primary systems may survive on weekly full backups made before January 15, and the Destruction Email acknowledges this. Recovery is estimated at \$3,000–\$5,000 per tape (Policy §4.3).

- Check whether the Salesforce/Veeva source data behind the destroyed "exports" still exists in the platforms, including the recycle bin and audit trail. Check whether copies exist in custodians' mailboxes, OneDrive, M365 retention, the vendors' systems or event-logistics vendors, and whether the KOL venue and caterer counterparties keep copies.

- Preserve the destruction record set: Q1_2025_Destruction_Log.xlsx, IT deletion certificates, the facilities shredding certificate, SM-CERT-2025-00412, the Nov. 19, 2024 Records Management Committee minutes, the Jan. 6 department-head notice, and the Jan. 13 Legal Hold Register check and response.

- HTM should run a privileged internal inquiry into (a) the earliest date Ridgeline had notice of a potential investigation (hotline logs, subpoenas, CIDs, HCP contacts, press) and (b) why the 6-year Categories L and M were destroyed on a 3-year schedule.

- Prepare the ¶46 written disclosure to DOJ, with volumes, dates and remediation, to be made promptly and before or alongside the March 17 certification.

## B. Suspension Has Not Yet Occurred

The Notice was effective March 3. As of the IT Memo, IT was waiting for Legal's authorization and estimated 24–48 hours to implement M365 holds. Every day of delay risks permanent loss through the 30-day Recoverable Items purge, 1-year IM expiry, 90-day voicemail purge, 2-year mobile retention, the CRM 2-year purge and the tape rotation. Any loss after March 3 is a post-Notice loss with direct §1519 and adverse-inference exposure. **Legal should issue the technical hold directive to IT (Policy §6.3) today.** Given ¶23's breadth, it should cover org-wide retention holds, not only the 23 custodians.

## C. The 2021 Email Migration Gap and the Legacy Exchange Servers

- **Facts.** Ashford Data Solutions' tool skipped archive and .pst stores larger than 4 GB held on separate volumes, for about 2,100 of 5,800 mailboxes. Ashford acknowledged the error (~Nov. 15, 2021). A \$280,000 re-migration was deferred in Q1 2022 and never funded in FY2023 or FY2024. About 340,000 emails from Jan. 2019–Sept. 2021 exist only on six powered-down Dell PowerEdge servers (Exchange 2016) at Sentinel Raleigh (SM-2247891), stored since Dec. 2021 and never verified. The custodian data is mixed in with the data of about 2,092 other employees.

- **The custodian cross-check is flawed.** The IT Memo's list of 8 includes "Jennifer Calloway, RSM Mid-Atlantic" and "David Yun, RSM West Coast." Neither appears in the Notice. Exhibit C lists Tonya Bradshaw as Mid-Atlantic RSM and has no West Coast region (James Okafor is Pacific Northwest). IT appears to have used an outdated or internal roster. **Actions:** (i) re-run the cross-check against the correct list of 23 (including the two functional-title custodians, once identified); (ii) keep Calloway and Yun on hold anyway, since their mailboxes may hold RSM-level KOL and field data; (iii) correct the "8 of 23" / "47,000–52,000 emails" figures before any statement to DOJ. The Org Chart repeats the "8 of 23" figure and should also be corrected.

- **Legacy tapes.** Legacy Exchange tapes (last ones covering about Sept.–Nov. 2021) were probably recycled. This is unconfirmed. IT should confirm today, in writing, through Sentinel's vault inventory.

- **Preservation versus recovery.** ¶42 requires the hardware to be kept "in current physical condition" and legacy systems kept accessible. Powering on drives that have been stored for three years risks failure, but leaving them untouched also risks further degradation. **Recommendation:** (i) send Sentinel a written hold today (no movement, disposal or environmental change; confirm chain of custody and the account is in good standing); (ii) have Greenwell (Dr. Anil Mukherjee) propose a forensic protocol, such as write-blocked imaging of each drive with no boot; (iii) **tell DOJ about the protocol before carrying it out** and get its written agreement, to avoid any claim of alteration under ¶¶35, 42.

- **Wider exposure.** Because ¶23 covers communications with all HCPs about Velcara, the un-migrated mailboxes of the other ~2,092 employees (field sales, MSLs) are also potentially in scope, not only the named custodians' mailboxes. Preserve the entire server set.

- **Documents.** Collect and preserve the Ashford services agreement (May 2021), incident report and acknowledgment, remediation proposal, Q1 2022 budget escalation memos, CFO-office decision records, the list of 2,100 affected users and the Sentinel inventory (Cats. 33–34). Send Ashford a preservation notice for its project files, scripts and logs. Consider Ashford's contractual liability separately. Note that Mr. Wardlow's memo is partly written to protect his own position ("a business prioritization decision made above my team's level"); HTM should interview him.

## D. RPAF — Can the Notice Bind It?

Paragraph 4 treats RPAF as a "related entity" bound "to the same extent as Ridgeline." The Org Chart and Policy §3.3 describe RPAF as a legally separate North Carolina 501(c)(3) organization. It has its own executive director, bank accounts, records and retention policy, and five directors, two of whom are independent (appointed to meet OIG independence guidance). Ridgeline does not control its day-to-day operations, and board action may be needed to adopt a hold. Richard Blaine is a liaison only.

- Ridgeline must preserve everything RPAF-related on Ridgeline systems now (Policy §3.3; ¶25).

- By **March 13**, send a written preservation notice directly to RPAF's executive director and full board, attaching the Notice and asking for written confirmation and a board resolution. Treat this in the same way as the third-party vendor notices.

- Suggest that RPAF retain its own counsel. Pressure from Ridgeline over RPAF operations could cut against the independence the OIG structure depends on.

- In the ¶45 certification and the letter to DOJ, describe accurately what Ridgeline can and cannot control. Ask DOJ whether it will serve RPAF directly.

- Identify the three Ridgeline-affiliated RPAF directors and treat them as hold recipients.

## E. Mobile Device Imaging (March 24)

- **External HCPs (Exh. D).** Ridgeline cannot compel five independent physicians and pharmacists to hand over personal devices. ¶40 as written cannot be carried out for them. Ask DOJ in writing to confirm that Ridgeline's obligation for Exhibit D is limited to Ridgeline-side data (which ¶¶15, 24 and Exh. D in fact describe) and to preservation letters sent to them as a courtesy. Any contact with these HCPs should be scripted by HTM to avoid any appearance of witness influence.

- **Employee personal devices.** Under Policy §4.5, full imaging requires consent or a court order. Get written consent (explaining the privacy protocol and filtering by Greenwell). Document any refusal and tell DOJ promptly. Individuals facing criminal exposure (e.g., Hsu, Terrell, Delgado, Osei) may need separate counsel and may assert Fifth Amendment rights over personal devices.

- **Privileged devices.** The GC's and CCO's devices contain privileged material. Imaging must be followed by a filter-team protocol.

- **Logistics.** About 18 employees in Durham, Atlanta, Philadelphia, Dallas, Chicago, Seattle and Denver, plus the CEO. Greenwell needs a schedule by March 10 to meet March 24 and to supply the ¶45(d) timeline.

## F. Linden & Pruitt and Dr. Osei — Privilege Complications

Paragraph 29 expressly reaches communications with Linden & Pruitt, P.A. about Velcara regulatory, FDA labeling and compliance advice (about 2020 to mid-2024). L&P is conflicted out because it separately represented Dr. Osei personally. Dr. Osei is a named custodian, was L&P's main business contact, and is affected by the migration gap. The Policy (§2.1) still lists L&P as current counsel. **Actions:** send L&P a preservation letter for its Ridgeline client files; do not use L&P for any hold or privilege work; set up a protocol for L&P materials in which privilege belongs to Ridgeline, not Dr. Osei, with segregated review; advise Dr. Osei to retain separate counsel; update Policy §2.1 and the templates.

## G. The General Counsel Is a Named Custodian and a Fact Witness

Mr. Ellsworth received the Notice and owns the Policy and the hold process. He is also custodian \#2, approved the Policy, and his office confirmed on January 13, 2025 that no holds applied to the January destruction. He is copied on the Destruction Email and approved the Policy's retention periods. **Recommendation:** HTM should direct and document the hold under Audit or Compliance Committee oversight. The ¶45(e) oversight designee should be a non-custodian (e.g., HTM together with an independent officer or a Board committee delegate). Mr. Ellsworth and Ms. Cho-Rosen (also a custodian and the Records Management reporting line) should be walled off from decisions about the January destruction inquiry.

## H. Financial Records Back to January 1, 2017 (¶47)

Policy Category D keeps general accounting records for 7 years. 2017 records would have become eligible for destruction during 2024 and early 2025, and 2018 records are due in the upcoming cycles. The Destruction Email says financial records were excluded from the January cycle, but earlier cycles (Apr., Jul., Oct. 2024) may have removed 2017 data. **Actions:** the CFO and Controller should confirm in writing what 2017–2018 GL, AP/AR, budget and payment data exists in SAP, archives and backups. Suspend Category B, C and D disposition. Report any gap under ¶46.

## I. Other Observations

- **International sites (London, Munich, Tokyo).** Preserving in place is lawful. Collecting or transferring data raises GDPR/UK GDPR and APPI issues, so involve local counsel before collection.

- **Physical Materials (¶3(c)).** Branded merchandise, samples and printed sales aids for Velcara must be withdrawn from disposal and pulped-inventory programs, including at print and fulfillment vendors.

- **Substantive note (for defense counsel, not preservation).** Each Exhibit D HCP averaged about \$5,500 per event and 35–70 events a year, well above the \$3,500 program average. The top 5 account for \$8.4M of the \$12.8M paid to the top 10. Expect a DOJ focus on FMV and frequency (Cats. 7, 14).

- **Policy maintenance.** Policy v2.0's annual review has been overdue since April 2023. Do not amend the Policy during the hold except to strengthen preservation; any change is itself in scope (¶5 "successor" policy).

- **Figures check.** The KOL annual totals (\$147.3M), RPAF annual totals (\$89.6M), top-10 payments (\$12.8M) and Destruction Email volumes (4.2M) all add up correctly. The only numerical inconsistencies found are the 36 vs. 34 categories and the IT Memo custodian list.

# IX. Third-Party Preservation Notice List (due March 13)

| **Recipient**                                                                                                                                                 | **Basis**                               | **Data / notes**                                                                                                                                                |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Veeva Systems                                                                                                                                                 | ¶43(a) (named)                          | Veeva CRM and Vault: call reports, samples, medical inquiries, MLR workflows; disable Cat. F purge                                                              |
| SAP SE                                                                                                                                                        | ¶43(b) (named)                          | SAP ERP financials from Jan. 1, 2017                                                                                                                            |
| Concur Technologies (SAP Concur)                                                                                                                              | ¶43(c) (named)                          | Expenses, receipts, HCP meals and travel                                                                                                                        |
| IntegriCall Services                                                                                                                                          | ¶43(d) (named)                          | Hotline intake, case files; override the 6-year addendum                                                                                                        |
| Sentinel Records Management (Raleigh; SM-2247891)                                                                                                             | ¶¶41, 42, 44                            | Backup tapes, 6 legacy Exchange servers, paper boxes. **No destruction orders to be honored.** Box and media inventory; audit trail for the Jan. 15 destruction |
| Salesforce                                                                                                                                                    | ¶38(a) ("including but not limited to") | CRM data, audit trail, recycle bin; source data for the destroyed exports                                                                                       |
| Microsoft (M365) / Slack (Salesforce)                                                                                                                         | ¶¶36, 37, 39                            | Mostly handled by tenant-level holds. Notice recommended for completeness and backups                                                                           |
| Ashford Data Solutions                                                                                                                                        | ¶¶30, 42; Cats. 33–34                   | Migration logs, scripts, project files, any residual data copies                                                                                                |
| Linden & Pruitt, P.A.                                                                                                                                         | ¶29; Cat. 32                            | Ridgeline client files, 2020–2024                                                                                                                               |
| RPAF (executive director and board)                                                                                                                           | ¶4                                      | See VIII.D. Not a vendor, but notice by Mar. 13 is recommended                                                                                                  |
| KOL event and logistics vendors, venues, speaker-bureau agencies, MDM/phone vendors, print and fulfillment vendors, the Atlanta and regional off-site storage | ¶43 ("all third-party vendors")         | Identify through AP vendor master data (SAP)                                                                                                                    |

# X. Recommended Action Plan

### Within 24–48 hours (by March 6–7)

1.  Legal/HTM issues the technical hold directive to IT: M365 litigation holds on all custodian mailboxes plus an org-wide retention hold; Teams, Slack and SharePoint/OneDrive set to indefinite; voicemail and CRM purges disabled; MDM wipes frozen.

2.  Pull all backup tapes from rotation (current environment and any legacy tapes). Get Sentinel's written vault inventory.

3.  Cancel the April 15 destruction cycle in writing. Instruct the Records Coordinator and Sentinel that no destruction may proceed without written HTM/DOJ authorization.

4.  Send Sentinel a written hold on SM-2247891 (servers, tapes, boxes).

5.  Secure paper at Durham and Atlanta (lock files, suspend shred-bin pickups).

6.  Identify the two functional-title custodians. Re-run the migration-gap cross-check against the correct list of 23.

7.  Issue individual hold notices to all 18 employee custodians and the extended list, with personal-account and device questionnaires. Acknowledgment within 2 business days.

8.  Instruct Greenwell to begin the device imaging schedule and to design the legacy-server forensic protocol.

### By March 13

9.  Send all third-party and RPAF preservation notices (Part IX). Begin tracking confirmations.

10. HTM contacts AUSA Faulkner and TA Gutierrez to raise clarification points (Part XI) and to preview the ¶46 disclosures.

11. Complete the tape-recovery assessment for data deleted Jan. 15, and the Salesforce/Veeva source-data check.

### By March 17

12. Serve the written ¶46 disclosure: Jan. 15 destruction, migration gap, legacy-tape status and any post-Notice loss.

13. Serve the ¶45 certification covering items (a)–(f), accurate and qualified, with the Exhibit C acknowledgments, the vendor notice list, the imaging timeline, the named oversight person and HTM as point of contact.

### By March 24 and ongoing

14. Complete forensic imaging with chain-of-custody logs. Report any device a custodian refused or could not produce.

15. Carry out the DOJ-agreed legacy Exchange server imaging protocol.

16. Quarterly hold reminders; process updates as DOJ supplements the list (¶¶18, 51); keep the privilege log protocol (¶48); run a privileged internal review of the January 2025 destruction and the migration-funding decisions.

# XI. Points to Clarify With DOJ (in writing, before March 13)

17. Receipt date and deadline computation (cover letter/¶1 "receipt" vs. ¶52 "mailing"). Confirm the stated dates control, or agree extensions for imaging.

18. The 36 vs. 34 categories, and whether HCP communications (¶¶23–24) are the two unnumbered categories. The ¶47 reference to "Area 7."

19. Whether mobile-imaging obligations for Exhibit D HCPs are limited to Ridgeline-side data; treatment of employee BYOD refusals.

20. DOJ agreement to the forensic protocol for the decommissioned Exchange servers (the ¶42 "current physical condition" requirement).

21. Whether DOJ will serve RPAF directly, given its independent governance.

22. The practical scope of ¶23 (all HCP communications about Velcara, by all employees) and of ¶31 (related compounds). Propose a reasonable framework: preserve org-wide in place, collect later by custodian.

23. Who the two functional-title custodians are, if DOJ has particular individuals in mind (e.g., prior incumbents).

# XII. Open Factual Questions

24. Actual FedEx delivery date and recipient of the Notice.

25. Earliest date Ridgeline had any notice of a government inquiry (hotline, subpoenas, CIDs, HCP contacts, qui tam unsealing), and whether any hold existed before January 13, 2025.

26. Whether the current backup tapes covering Oct. 2024–Jan. 2025 still exist; whether legacy Exchange tapes survive.

27. Who Jennifer Calloway and David Yun are, and the source of the IT roster.

28. Contents of the 47 destroyed Sentinel boxes and of the remaining Sentinel inventory.

29. Status of 2017–2018 financial data and of any 2024 destruction cycles.

30. Identities of the Ridgeline-affiliated RPAF directors; RPAF's own retention practices and systems.

31. Which custodians use personal devices, personal email or ephemeral messaging apps for business.

32. Current Slack, Teams, voicemail and CRM retention configurations, and whether any automatic deletion has run since March 3, 2025.

*This memo is based only on the five documents listed in Part II and has not been independently verified. Deadlines and recommendations should be confirmed by responsible outside counsel. Nothing in this memo should be communicated to the government except through HTM.*
