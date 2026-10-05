# Case-citation check of the 19 sampled task environments

> [!WARNING]
> **AI-generated, spot-checked analysis.** One Opus agent per task extracted every case citation in the task instructions, rubric and supplied documents and checked it against CourtListener (with web search as a fallback); an Opus synthesis agent wrote this report and re-verified a sample of findings, and the coordinating session independently re-checked seven of them. "Not found" means not found after a thorough search, not proof of fabrication. Characterizations of holdings are AI judgments. Fictional-by-design material (the tasks' own captions and in-universe orders) is excluded. See the [human-review protocol](README.md).


**Scope:** Harvey Legal Agent Benchmark (LAB), `litigation-dispute-resolution` practice area, `harveyai/harvey-labs` pinned at commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`. The 19 task environments are the ones that contain the 25 criteria sampled in the human review worksheet (`docs/harvey-lab-audit/litigation-dispute-resolution/human-review/worksheet.md`).

**Method:** One verification agent per task extracted every supplied document and the task's `task.json` (instructions and all rubric criteria):

- DOCX through pandoc, plus header, footer, comment and footnote parts where present
- XLSX through openpyxl, covering every sheet, cell and comment
- EML through Python's `email` module, covering every MIME part

Each agent swept the text with eyecite and regex for reporter citations, `X v. Y` captions, `In re`, Westlaw and Lexis cites, and case names given without a citation. It then checked every case authority against CourtListener using `analyze_citations`, `search`, `search_document` and `read_document`, and used web search to back up any null results. Characterizations were tested by literal phrase searches against the opinion text and by reading the cited pages. I spot-checked a sample of the most consequential findings myself (see §5.1).

---

## 1. Executive summary

**Counting unit.** The basic unit in this report is a **citation instance**: one citation as written, in one document, for one proposition. A few authorities are cited in two documents of the same task with different accuracy. For example, *Benchmark* is mischaracterized in the research memo and cited correctly in the standing order. Counting instances keeps those cases distinct. Where useful, I also give within-task unique counts and counts deduplicated across tasks.

**What was checked**

- **19 tasks; 193 environment files:** 174 supplied documents plus 19 `task.json` instruction and rubric files. The repo-side audit reports and model-run outputs were read for context only.
- **6 of the 19 tasks cite no real or purported judicial authority anywhere:** compare-document-production, draft-case-assessment-memorandum, draft-conflict-check-memorandum, draft-counterclaim, draft-discovery-plan-memorandum, and identify-issues-in-matter-budget-proposal.
- **102 citation instances to purported real judicial authority.** These are 97 unique citations within tasks, and 91 after removing repeats across tasks (*Daubert* appears in 5 tasks; *Carden* and *Formosa* in 2 each).
- **48 fictional-by-design items** are reported separately and are never counted as problems. They include the tasks' own captions, in-universe court orders, firm matter numbers and expert-CV matters.

**Results by citation instance (n = 102)**

| Outcome | Instances |
|---|---|
| Verified (exists; proposition supported) | **57** |
| &nbsp;&nbsp;of which no defect noted | 41 |
| &nbsp;&nbsp;of which verified with a minor defect noted (pin, quote source, loose parenthetical; see §5.3) | 16 |
| **Problem citations** | **45** |
| &nbsp;&nbsp;VERIFIED_BUT_MISCHARACTERIZED (real case, cited for a holding, quotation or facts it does not contain or contradicts) | 32 |
| &nbsp;&nbsp;NOT_FOUND_LIKELY_FABRICATED (no such case located after thorough search) | 7 |
| &nbsp;&nbsp;WRONG_CITATION_REAL_CASE (a real case exists, but the reporter, court, page or party is garbled) | 5 |
| &nbsp;&nbsp;CITATION_POINTS_TO_DIFFERENT_CASE (real reporter cite, invented case name) | 1 |

The 45 problem instances collapse to 43 problem entries in the §2 table: *Melody Home* and *Cendant* are each miscited in two documents of the same task and are shown on one row each.

**Concentration**

- **5 of 19 tasks contain at least one problem.**
- Two tasks account for 38 of the 45 problem instances:
  - **draft-motion-to-dismiss-brief:** 28 problem instances of 53.
  - **review-counterpartys-proposed-jury-instructions:** 10 of 21.
- The other three tasks with problems:
  - draft-responses-to-interrogatories: 4 of 9
  - draft-interrogatories: 2 of 6
  - identify-excessive-or-duplicative-research-charges: 1 of 2

**Relatedness of the 43 problem entries to the task:** 8 central, 19 related, 14 peripheral, 2 unrelated.

The 8 central entries all sit under rubric criteria that either name the defective authority or rest on a rule supported only by it:

- MTD C-023: *Brasby*, *Kuhn*
- MTD C-024: *Chapman*, *Sharyland*
- MTD C-037: *SIGA*, *Eagle Industries*
- Jury-instructions C-019/C-020: *Disaster Services*, *Valdosta Livestock*

**Sampled worksheet items.** Of the 25 sampled criteria, two depend directly on defective case law:

- **Item #17 (MTD C-037).** The rubric rewards citing *SIGA* and *Eagle Industries* as Delaware parol-evidence authority, and neither supports the proposition. Both model runs failed. The Opus 5.5 run caught both defects and cited the correct authority, *Abry Partners*.
- **Item #23 (jury-instructions C-020).** The criterion requires a Georgia tortious-interference rule. Its only cited authorities are one real case that states the opposite rule and one case that could not be found.

One more item touches case law indirectly. Item #4 concerns the GPT-6 Sol audit's own citation: *Oregon JV v. Advance Investment Corp.* is real, though misspelled "Advanced". The other 22 sampled criteria do not involve case law.

---

## 2. Problem citations

**Status key:**

- **MISCHAR** = VERIFIED_BUT_MISCHARACTERIZED
- **NOT FOUND** = NOT_FOUND_LIKELY_FABRICATED
- **WRONG CITE** = WRONG_CITATION_REAL_CASE
- **DIFF CASE** = CITATION_POINTS_TO_DIFFERENT_CASE

**Rubric column:**

- **names** = a criterion names the case
- **depends** = a criterion depends on the proposition without naming the case
- **none** = no criterion names or depends on it

"CL" = CourtListener cluster ID.

| # | Task | Document / locator | Citation as written | Status | What is actually true | Relatedness | Rubric |
|---|---|---|---|---|---|---|---|
| 1 | draft-motion-to-dismiss-brief | Research memo §VII.A | *SIGA Techs., Inc. v. PharmAthene, Inc.*, 67 A.3d 330, 344 (Del. 2013) | MISCHAR | Real (CL 5146572). The opinion is about a duty to negotiate in good faith, expectation damages and promissory estoppel. "Integration clause", "parol evidence", "extrinsic" and "clearest declaration" each return 0 hits; the quoted sentence is absent. | central | names C-037 |
| 2 | draft-motion-to-dismiss-brief | Research memo §VII.B, §XII.A | *Eagle Indus., Inc. v. DeVilbiss Health Care, Inc.*, 702 A.2d 1228, 1232 (Del. 1997) | MISCHAR | Real (CL 2395434). The case is an indemnification-ambiguity dispute with no fraud claim. It admits extrinsic evidence "notwithstanding the presence of a routine integration clause" (n.10). The quoted "cannot promise" sentence is absent. | central | names C-037 |
| 3 | draft-motion-to-dismiss-brief | Research memo §IV.A.1 | *Brasby v. Morris Dynamics, Inc.*, 947 A.2d 1042, 1049-50 (Del. 2008) | WRONG CITE | No such reporter cite or Delaware Supreme Court opinion. The real case is *Brasby v. Morris*, 2007 WL 949485 (Del. Super. Ct. Mar. 29, 2007) (unpublished). The party name, court, year, facts and quotations are invented. | central | names C-023 |
| 4 | draft-motion-to-dismiss-brief | Research memo §IV.A.2, §XII.B | *Kuhn Constr., Inc. v. Diamond State Port Corp.*, 990 A.2d 393, 401-02 (Del. 2010) | MISCHAR | Real (CL 1484430). It is an arbitration (referee-clause) case; "economic loss" returns 0 hits. The pins 401-02 fall beyond the last star page (*398). | central | names C-023 |
| 5 | draft-motion-to-dismiss-brief | Research memo §IV.B.2 | *Chapman Custom Homes, Inc. v. Dallas Plumbing Co.*, 445 S.W.3d 716, 718-19 (Tex. 2014) | MISCHAR | Real (CL 2831423). The Court **reversed**; the economic loss rule "does not apply here." The three-factor test and the quotation are absent. | central | names C-024 |
| 6 | draft-motion-to-dismiss-brief | Research memo §IV.B.1 | *Sharyland Water Supply Corp. v. City of Alton*, 354 S.W.3d 407, 415-16 (Tex. 2011) | MISCHAR | Real (CL 5281308). Held the rule does **not** bar the negligence claim. The quoted "contractual expectancy" sentence comes from *Chapman* (quoting *LAN/STV*). | central | names C-024 |
| 7 | draft-motion-to-dismiss-brief | Research memo §III.A | *Benchmark Elecs., Inc. v. J.M. Huber Corp.*, 343 F.3d 719 (5th Cir. 2003) | MISCHAR | Real (CL 8437769). A stock purchase, not a chemical sale. The 9(b) dismissal was **vacated**. The "who, what, when, where, and how" language at 724 is accurate. | related | names C-021, C-081 |
| 8 | draft-motion-to-dismiss-brief | Research memo §III.B | *Dorsey v. Portfolio Equities, Inc.*, 540 F.3d 333, 339-40 (5th Cir. 2008) | MISCHAR | Real (CL 63256). Affirmed in part, **reversed** in part (fraud claims reinstated). The 9(b) standard at 339 is accurate. | related | names C-021, C-081 |
| 9 | draft-motion-to-dismiss-brief | Research memo §III.C | *Flaherty & Crumrine Preferred Income Fund v. TXU Corp.*, 565 F.3d 200, 207-08 (5th Cir. 2009) | MISCHAR | Real (CL 65375). It says common-law fraud is **not** subject to the PSLRA "strong inference" standard; Rule 9(b) applies. | related | names C-021 |
| 10 | draft-motion-to-dismiss-brief | Research memo §II.C | *Lormand v. US Unwired, Inc.*, 565 F.3d 228 (5th Cir. 2009) | MISCHAR | Real (CL 65339), decided 2009-04-09, before *Iqbal* (May 18, 2009), so it cannot quote *Iqbal*. The quoted language was not found. Dismissal reversed in part. | related | names C-081 |
| 11 | draft-motion-to-dismiss-brief | Research memo §VIII.B | *Pizza Hut, Inc. v. Papa John's Int'l, Inc.*, 227 F.3d 489, 498-99 (5th Cir. 2000) | MISCHAR | Real (CL 22001). The definition of puffery at 496-97 is accurate. The context rule is stated backwards: in context the slogan "became misleading and actionable". | related | names C-048, C-081 |
| 12 | draft-motion-to-dismiss-brief | Research memo §VIII.C | *Presidio Enters. v. Warner Bros. Distrib. Corp.*, 784 F.2d 674, 679-80 (5th Cir. 1986) | MISCHAR | Real (CL 465209). The core puffery and sophisticated-reliance holding is supported. The quotation is absent, and the facts are wrong (one film, *The Swarm*; a DTPA verdict). | related | names C-048, C-081 |
| 13 | draft-motion-to-dismiss-brief | Research memo §VI.B | *Excess Underwriters at Lloyd's v. Frank's Casing Crew*, 246 S.W.3d 42, 59-60 (Tex. 2008) | MISCHAR | Real (CL 1402310). The core express-contract bar is supported. The facts are inverted, and the "same subject" quotation and the "no gap" holding are absent. | related | names C-029 |
| 14 | draft-motion-to-dismiss-brief | Research memo §XI.A | *McCamish, Martin, Brown & Loeffler v. F.E. Appling Interests*, 991 S.W.2d 787, 792 (Tex. 1999) | MISCHAR | Real (CL 1533840). "Independent duty" means independent of **privity** (liability to non-clients), not of a contract between the parties. The elements are accurate. | related | names C-040 |
| 15 | draft-motion-to-dismiss-brief | Research memo §XI.B | *Fed. Land Bank Ass'n of Tyler v. Sloane*, 825 S.W.2d 439, 442-43 (Tex. 1991) | MISCHAR | Real (CL 2396129). The Sloanes **won** out-of-pocket damages; the claim was not "barred". The damages limit and elements are accurate. | related | names C-040 |
| 16 | draft-motion-to-dismiss-brief | Research memo §IX.A | *Dresser-Rand Co. v. Virtual Automation Inc.*, 361 F.3d 831, 838-40 (5th Cir. 2004) | MISCHAR | Real (CL 34433). A dispute over a former employee and misappropriation of confidential information; no software-license liability-cap holding; "Delaware" returns 0 hits. | related | C-081 catch-all ("any other Fifth Circuit authority from the research memo") |
| 17 | draft-motion-to-dismiss-brief | Research memo §IX.B | *Kana Software, Inc. v. Sealand Technology, Inc.*, 178 A.3d 1045 (Del. Ch. 2017) | NOT FOUND | No case at that cite or by that name in CourtListener or on the web. The facts mirror the task's MSLSA. | related | none |
| 18 | draft-motion-to-dismiss-brief | Research memo §X.A | *Simulados, Inc. v. Canton Health Mgmt. Co.*, 2019 WL 4573218 (W.D. Tex. Sept. 20, 2019) | NOT FOUND | No such case. The only "Simulados" case is *Simulados Software v. Photon Infotech*, 40 F. Supp. 3d 1191 (N.D. Cal. 2014), which is unrelated. | related | none |
| 19 | draft-motion-to-dismiss-brief | Research memo §X.B | *Precision Healthcare Solutions v. Nextera Data Systems*, 458 F. Supp. 3d 544 (N.D. Tex. 2020) | NOT FOUND | No case at that cite or by that name. | related | none |
| 20 | draft-motion-to-dismiss-brief | Research memo §V.C | *PPG Indus. v. JMB/Houston Ctrs. Partners*, 146 S.W.3d 79, 89 (Tex. App.—Houston [1st Dist.] 2004, no pet.) | MISCHAR | Real (CL 894577), but it is a **Texas Supreme Court** decision on whether DTPA claims are assignable. The §17.49(f) "total consideration" holding is absent. | related | none (C-025, C-026 and C-089 concern the exemption) |
| 21 | draft-motion-to-dismiss-brief | Research memo §XII.A | *Hollcroft & Sedgewick, L.L.P. v. Pacific Mut. Life Ins. Co.*, 51 S.W.3d 573, 577 (Tex. 2001) | DIFF CASE | 51 S.W.3d 573 is *Ernst & Young, L.L.P. v. Pacific Mut. Life Ins. Co.* (CL 1579057). The party name is invented; the reliance proposition at 577 survives under the correct name. | peripheral | none |
| 22 | draft-motion-to-dismiss-brief | Research memo §V.A | *Riverside Nat'l Bank v. Lewis*, 603 S.W.2d 169, 173 (Tex. 1980) | MISCHAR | Real (CL 1624043). Held Lewis was **not** a consumer. (The Meridian letter's cite to the same case is accurate.) | peripheral | none |
| 23 | draft-motion-to-dismiss-brief | Research memo §V.B; Arcadia DTPA letter §I (two instances) | *Melody Home Mfg. Co. v. Barnes*, 741 S.W.2d 349, 351-52, 355 (Tex. 1987) | MISCHAR | Real (CL 1730755). An implied-warranty case. The memo's producing-cause holding is absent. The letter's "does not distinguish between sophisticated and unsophisticated consumers" returns 0 hits across all four opinions. | peripheral | none |
| 24 | draft-motion-to-dismiss-brief | Arcadia DTPA letter §II | *Cameron v. Terrell & Garrett, Inc.*, 618 S.W.2d 535, 541 (Tex. 1981) | MISCHAR | Real (CL 1527473). No holding that DTPA exemptions are affirmative defenses ("affirmative" returns 0 hits). | peripheral | none |
| 25 | draft-motion-to-dismiss-brief | Meridian DTPA response letter §III | *Fortis Benefits v. Cantu*, 234 S.W.3d 642, 649 (Tex. 2007) | MISCHAR | Real (CL 894884). A contractual-subrogation case; "unjust enrichment" returns 0 hits. The support is only by analogy. | peripheral | none |
| 26 | draft-motion-to-dismiss-brief | First amended complaint appendix (Count I) | *Valero Mktg. & Supply Co. v. Kalama Int'l*, 51 S.W.3d 345 (Tex. App.—Houston [1st Dist.] 2001) | MISCHAR | Real (CL 1579210). A methanol sales contract, not a "software licensing agreement". | unrelated | none |
| 27 | draft-motion-to-dismiss-brief | First amended complaint appendix (Count II) | *Haase v. Glazner*, 62 S.W.3d 795 (Tex. 2001) | MISCHAR | Real (CL 1353594). About fraudulent inducement and the Statute of Frauds, not nondisclosure ("disclos" returns 0 hits). | unrelated | none |
| 28 | review-counterpartys-proposed-jury-instructions | Summary-judgment order §IV.E | *Disaster Servs., Inc. v. ERC P'ship*, 228 Ga. App. 739, 740 (1997) | MISCHAR | Real (CL 1388876). At 740, **all** interference claims, including those on contractual relations, require "(1) improper action or wrongful conduct by the defendant without privilege" and malice. That contradicts the four-element test it is cited for. | central | depends C-019, C-020 |
| 29 | review-counterpartys-proposed-jury-instructions | Summary-judgment order §IV.E | *Valdosta Livestock, Inc. v. Furst*, 342 Ga. App. 25, 28 (2017) | NOT FOUND | 342 Ga. App. 25 falls within *Hosp. Auth. of Valdosta/Lowndes Cnty. v. Fender*, 342 Ga. App. 13 (CL 4406052). The only "Valdosta Livestock" cases are *Valdosta Livestock Co. v. Williams* (E.D.N.C. 1962; 4th Cir. 1963). | central | depends C-019, C-020 |
| 30 | review-counterpartys-proposed-jury-instructions | Summary-judgment order §IV.B (full and short cites) | *Hoshizaki Am., Inc. v. Heil*, 338 Ga. App. 38, 44 (2016) | NOT FOUND | 338 Ga. App. 38 falls within *Abdalla v. Atlanta Nephrology Referral Ctr.*, 338 Ga. App. 36 (CL 4239192). No case with Hoshizaki as a party. | related | depends C-011 (proposition is also statutory) |
| 31 | review-counterpartys-proposed-jury-instructions | Summary-judgment order §IV.C | *Cochran v. Ogletree*, 244 Ga. App. 828, 833 (2000) | WRONG CITE | 244 Ga. App. 828 is *Sims v. State*. The real *Cochran v. Ogletree*, 244 Ga. App. 537 (CL 1341754), is a construction-deposit refund case with no trade-secret content. | related | depends C-001, C-002 (via the order's ruling) |
| 32 | review-counterpartys-proposed-jury-instructions | Defense proposed Instruction No. 15; summary-judgment order §IV.B | *Penalty Kick Mgmt. Ltd. v. Coca Cola Co.*, 318 Ga. App. 586 (2012) | WRONG CITE | 318 Ga. App. 586 is *Dodson v. Walraven* (CL 7928139). The real case is 318 F.3d 1284 (11th Cir. 2003) (CL 780794). The plaintiff's brief in the same record cites it correctly. | related | C-029 offers No. 15 as an unobjectionable instruction |
| 33 | review-counterpartys-proposed-jury-instructions | Plaintiff's trial brief §II.A | *Univ. Computing Co. v. Lykes-Youngstown Corp.*, 504 F.2d 518, 535 (5th Cir. 1974) | MISCHAR | Real (CL 8907488). Treats plaintiff's loss and defendant's gain as **alternative** measures, not complementary ones. | related | none (C-013 is statute-based) |
| 34 | review-counterpartys-proposed-jury-instructions | Plaintiff's trial brief §III.C | *Penalty Kick Mgmt. Ltd. v. Coca Cola Co.*, 318 F.3d 1284, 1298 (11th Cir. 2003) | MISCHAR | Page 1298 concerns GTSA supersession. The opinion **rejects** the plaintiff's circumstantial inferences (1293-94). | peripheral | none |
| 35 | review-counterpartys-proposed-jury-instructions | Plaintiff's trial brief §III.C | *MiMedx Grp., Inc. v. Sparks*, No. 1:18-cv-04332, 2020 WL 7626433 (N.D. Ga. Dec. 22, 2020) | NOT FOUND | N.D. Ga. 1:18-cv-04332 is *Ombonga v. Triage Consulting Group*. No *MiMedx v. Sparks* found. | peripheral | none |
| 36 | review-counterpartys-proposed-jury-instructions | Summary-judgment order §IV.D | *Paramount Tax & Accounting v. H & R Block E. Enters.*, 299 Ga. App. 791, 796 (2009) | WRONG CITE | The real case is at 299 Ga. App. 596 (CL 1375412); 791 is *Walker v. State*. It does not discuss confidentiality versus noncompete provisions. | peripheral | none |
| 37 | review-counterpartys-proposed-jury-instructions | Summary-judgment order §IV.B | *Reingold v. Swiftships, Inc.*, 126 F.3d 645, 648 (5th Cir. 1997) | MISCHAR | Real (CL 746885). Never discusses circumstantial evidence (0 hits). | peripheral | none |
| 38 | draft-responses-to-interrogatories | Client-interview memo §IV.A; discovery-response guidelines §V.C (two instances) | *In re Cendant Corp. Sec. Litig.*, 343 F.3d 658, 662 (3d Cir. 2003) | MISCHAR | Real (CL 783536). A trial-consultant work-product case; "primary" and "motivat" return 0 hits. The "primary motivating purpose" test comes from *United States v. Rockwell Int'l*, 897 F.2d 1255, 1266 (3d Cir. 1990). | related | none (C-012 tests the issue but does not name the case) |
| 39 | draft-responses-to-interrogatories | Discovery-response guidelines (deadlines) | *Exxon Corp. v. FTC*, 588 F.2d 895 (3d Cir. 1978) | MISCHAR | Real. An FTC confidentiality and declaratory-judgment case; no discussion of waiver of discovery objections ("waive" returns 0 hits). | peripheral | none |
| 40 | draft-responses-to-interrogatories | Discovery-response guidelines (deadlines) | *Safeco Ins. Co. of Am. v. Rawstron*, 181 F.R.D. 441 (C.D. Cal. 1998) | MISCHAR | Real (CL 9052770). About counting Rule 33 discrete subparts; nothing on waiver; not "of this circuit". | peripheral | none |
| 41 | draft-interrogatories | In-universe TRO order §IV.B | *Tex. Advanced Optoelectronic Sols. v. Renesas Elecs. Am.*, 895 F.3d 1304, 1315 (Fed. Cir. 2018) ("applying Fifth Circuit law") | MISCHAR | Real (CL 8440002). Page 1315 concerns contractual permitted use. The irreparable-harm discussion concerns a **patent** injunction under *eBay*. "Unlearn" returns 0 hits. | peripheral | none |
| 42 | draft-interrogatories | In-universe TRO order §IV.B | *FMC Corp. v. Taiwan Taiyo Yuden Co.*, 743 F.2d 1470, 1473 (Fed. Cir. 1984) | WRONG CITE | The real case is *FMC Corp. v. Taiwan Tainan Giant Indus. Co.*, 730 F.2d 61, 63 (2d Cir. 1984) (CL 433035): "A trade secret once lost is, of course, lost forever." The as-written cite lands in *United States v. Esle* (11th Cir.). | peripheral | none |
| 43 | identify-excessive-or-duplicative-research-charges | July 2024 invoice, cell I52 (Hargrove, 07/17/2024) | *Thompson v. Pacific Envtl. Corp.* ("recent Washington Supreme Court decision") | NOT FOUND | No such decision found. Nearest names are unrelated (*Thompson v. East Pacific Enterprises*, Wash. App. 2003, unpublished). Probably invented background detail inside a fictional time entry. | peripheral | none (C-007 to C-010 and C-039 depend on the time entry, not the case) |

---

## 3. Central and related problems in detail

### 3A. draft-motion-to-dismiss-brief (worksheet items #17, #18)

The task supplies a "Key Case Law Compilation" defense research memo with 31 authorities:

- **8 are accurate:** *Twombly*, *Conley*, *Iqbal*, *Fortune*, *Castrol*, *Harvey v. Grey Wolf*, *Carden*, *Arbaugh*.
- **23 have problems:**
  - 18 are real cases cited for a holding, quotation or facts they do not contain
  - 3 could not be found
  - 1 is a bogus reporter cite for a real unpublished case
  - 1 is an invented name on a real reporter cite

The rubric (89 criteria) names many of these authorities as models for the brief to cite.

**C-037: Delaware parol-evidence authority (*SIGA*, *Eagle Industries*). Worksheet item #17.**

*SIGA.* The memo quotes *SIGA*, 67 A.3d at 344, for "an integration clause is the clearest declaration that the parties intend the writing to be the complete and final expression of their agreement." It treats the case as barring claims based on prior representations.

- Literal searches of the *SIGA* opinion return 0 hits for "integration clause", "clearest declaration", "parol evidence" and "extrinsic". I re-ran the "integration clause" search myself on the lead opinion: 0 hits.
- The only integration reference is to promissory estoppel: "Promissory estoppel does not apply, however, where a fully integrated, enforceable contract governs the promise at issue" (fn. 74).
- The actual holdings concern the enforceability of an agreement to negotiate in good faith, expectation damages, and reversal on promissory estoppel.

*Eagle Industries.* The memo quotes it at 1232 for "a party to a contract cannot promise, in a clear integration clause of a negotiated agreement, that it is not relying on promises or representations ... and then assert a claim for fraud based on those very representations."

- That sentence does not appear in the opinion. I re-ran the "cannot promise" search myself: 0 hits.
- *Eagle* is an indemnification dispute with no fraud claim. It held the provision "ambiguous, thus raising factual issues requiring consideration of extrinsic evidence." It also notes that prior communications may be considered "notwithstanding the presence of a routine integration clause" (fn. 10). The holding therefore cuts against the memo's use.

*How the rubric and the model runs handled it.*

- C-037 passes a brief that cites authority "such as SIGA" or *Eagle*.
- The live doctrine is contractual non-reliance in a fraud-in-the-inducement claim, not parol evidence. The accurate Delaware authority is *Abry Partners V, L.P. v. F&W Acquisition LLC*, 891 A.2d 1032, 1058-59 (Del. Ch. 2006). It holds that "standard integration clauses without explicit anti-reliance representations, will not relieve a party of its oral and extra-contractual fraudulent representations" and enforces a clear anti-reliance clause. MSLSA §12.1 contains exactly such an express non-reliance sentence. *Abry* is cited, and verified, in Meridian's own DTPA response letter in the record.
- **Claude Opus 5.5 (low)** flagged *SIGA* and *Eagle* in a citation-problems table, declined to cite them, and cited *Abry*, *Kuroda* and *VLIW* instead. It was **failed by both judges** (Sonnet 4.6 and GPT-5.5). One caveat: Opus's own description of *Eagle* restated the *Abry*/*Kronenberg* rule rather than *Eagle*'s actual ambiguity holding.
- **GPT-6 Luna (xhigh)** cited no Delaware authority and also failed.
- The Opus 5.5 AI audit (O9) had flagged *SIGA*.

The result: the one run that detected the defect and substituted correct authority received the same score as a run that cited nothing.

**C-023: Delaware economic loss doctrine (*Brasby*, *Kuhn*).**

*Brasby.* The memo describes *Brasby v. Morris Dynamics, Inc.*, 947 A.2d 1042 (Del. 2008), as a Delaware Supreme Court affirmance dismissing fraud claims over an industrial automation system, and quotes it at 1049-50.

- 947 A.2d 1042 is not found in CourtListener (I re-verified this), and a name search finds no such Supreme Court case.
- Later Delaware Superior Court opinions do cite *Brasby v. Morris*, 2007 WL 949485 (Del. Super. Ct. Mar. 29, 2007), for "there is no reason to extend tort law into areas that can be adequately governed by contract law."
- So a real unpublished trial-court economic-loss case lies underneath. The party name, court, year, reporter, facts and quotations in the memo are all wrong.

*Kuhn.* *Kuhn Construction*, 990 A.2d 393, is a referee-clause arbitration decision: "Because the referee clause on these facts do not clearly require arbitration ... we reverse." It has no economic-loss discussion (0 hits). The memo's pins (401-02) lie past the opinion's last star page (*398).

*How the rubric and the model runs handled it.*

- C-023 names both cases ("such as Brasby v. Morris Dynamics").
- Both runs failed C-023 under both judges.
- Opus flagged *Brasby* as apparently nonexistent and *Kuhn* as mischaracterized.
- Luna rejected the categorical economic-loss theory under Texas law (*Formosa Plastics*).
- The Opus 5.5 audit (O7) flagged both cases.

**C-024: Texas economic loss rule (*Chapman*, *Sharyland*).**

*Chapman.* The memo says *Chapman Custom Homes*, 445 S.W.3d 716, "reaffirmed" the bar, sets out a three-factor test, and holds that "the plaintiff's remedy is in contract alone." The per curiam opinion, which I re-verified, reverses: "Although the court of appeals views this property damage as a mere economic loss ... and purports to apply the economic loss rule as a bar to any tort claim, the rule does not apply here." No three-factor test appears in it.

*Sharyland.* *Sharyland*, 354 S.W.3d 407, held that "the economic loss rule does not preclude a negligence claim against the contractors." The memo's quotation attributed to it ("generally precludes recovery in tort for economic losses ... contractual expectancy") comes from *Chapman* quoting *LAN/STV*. My own *Chapman* search retrieved that exact sentence in *Chapman*.

*How the rubric and the model runs handled it.*

- C-024 names both cases as models for dismissing the tort claims, although both decisions went against the party invoking the rule.
- Both runs failed C-024 under both judges.
- Luna argued, accurately, that Texas's rule is not a categorical bar to fraudulent inducement, and was failed for it.

**C-021 / C-081: Rule 9(b) and Fifth Circuit pleading authority (*Benchmark*, *Dorsey*, *Flaherty*, *Lormand*).** Each case is real and states the pleading standard for which the rubric names it, so the rubric's use is sound. The memo's narratives are wrong:

- ***Benchmark*** is described as affirming a 9(b) dismissal over a "specialty chemical compound." The case was a stock purchase (AVEX). The court held "Benchmark's fraud and misrepresentation pleadings withstand a lack of particularity challenge under Rule 9(b)" and vacated. Its "who, what, when, where, and how" language at 724 is accurate, and the in-universe standing order uses it correctly.
- ***Dorsey*** is described as "affirmed." The court affirmed in part and reversed in part ("Dorsey sufficiently pleaded scienter").
- ***Flaherty*** is cited for a 9(b) "strong inference" requirement. The opinion says "common law fraud claims are not subject to the heightened 'strong inference' of scienter standard imposed by the PSLRA," though they remain subject to Rule 9(b).
- ***Lormand*** is said to apply and quote *Iqbal*. It was decided April 9, 2009 (I re-verified the date), before *Iqbal* (May 18, 2009).

Both runs passed C-021 and C-081. Luna cited *Benchmark* at 724 and *Dorsey* at 339 accurately. Opus flagged the memo's errors.

**C-048: Puffery (*Pizza Hut*, *Presidio*).**

- ***Pizza Hut*:** the definition of puffery (496-97) is accurate. The memo's claim that puffery "remains non-actionable" even when paired with specific factual claims is the reverse of the holding: "when the slogan is used in this context, it is no longer mere opinion, but rather takes on the characteristics of a statement of fact," and it "became misleading and actionable." Papa John's prevailed only because materiality was not shown.
- ***Presidio*:** the core holding is supported ("Presidio's executives were experienced, professional film exhibitors who could not reasonably have relied on Warner's puffery"). However, the memo's block quotation ("was in at least as good a position as Warner Bros. ...") returns 0 hits, and the case involved one film and a DTPA verdict.

Both runs passed C-048, and Opus noted that the memo "gets [Pizza Hut] backwards."

**C-029: Express-contract bar to unjust enrichment (*Excess Underwriters*).** The memo inverts the parties and attributes a quotation ("'not proper' where 'the same subject' is covered") that returns 0 hits. The real related sentence is "[w]hen a valid agreement already addresses the matter, recovery under an equitable theory is generally inconsistent with the express agreement" (quoting *Fortune*, 52 S.W.3d at 684). The core proposition holds. Both runs passed; Luna cited it alongside *Fortune*.

**C-040: Negligent misrepresentation (*McCamish*, *Sloane*).**

- ***McCamish*** extends §552 liability to non-clients: "liability is not based on the breach of duty a professional owes his or her clients or others in privity, but on an independent duty to the non-client." The memo turns "independent" (of privity) into "independent of any contractual obligations." The criterion's duty theory therefore lacks the support the memo claims. The Opus audit (O8) flagged this.
- ***Sloane*:** the plaintiffs won out-of-pocket damages, with judgment on remand for $11,427.03, rather than having their claim "barred." The §552B damages limitation is accurately stated.

Both runs passed C-040 citing the cases for their accurate propositions.

**Memo authorities not named in the rubric (related).**

- ***Dresser-Rand*** (361 F.3d 831) is the memo's lead authority for enforcing the MSLSA liability caps (C-031 to C-033). It is a misappropriation and fraud case with no liability-cap holding. C-081's catch-all for "any other Fifth Circuit authority from the research memo" would credit citing it.
- ***Kana Software v. Sealand*** (178 A.3d 1045, Del. Ch. 2017) is presented as factually analogous on caps. It was not found: I re-verified the citation lookup and a caseName search, both of which return nothing.
- ***Simulados v. Canton Health*** (2019 WL 4573218) and ***Precision Healthcare v. Nextera*** (458 F. Supp. 3d 544) are the memo's only authority for the deemed-acceptance argument (C-034, C-035, C-084). Neither was found, and both fact patterns mirror the task's 30-day acceptance clause.
- ***PPG*** is cited as a Houston court of appeals case for a §17.49(f) "total consideration" holding. It is a Texas Supreme Court decision on whether DTPA claims are assignable.

Opus flagged *Kana*, *Simulados* and *Precision* as nonexistent. It declined to make the deemed-acceptance argument at all rather than rely on them. Luna cited none of the five. The verifier did not report how either run was graded on C-034/C-035/C-084.

Worksheet item #18 (C-045, Arcadia's own delays) is a factual criterion with no case-law dependency.

### 3B. review-counterpartys-proposed-jury-instructions (worksheet item #23)

**C-019 / C-020: Georgia tortious interference (*Disaster Services*, *Valdosta Livestock*). Worksheet item #23.**

*What the environment says.* The fictional summary-judgment order (§IV.E) lists the elements of tortious interference with an existing contract as:

1. a valid contract
2. the defendant's knowledge of it
3. intentional inducement of breach
4. damages

There is no wrongful-conduct element. Its only authorities are *Disaster Services, Inc. v. ERC Partnership*, 228 Ga. App. 739, 740 (1997), and "*Valdosta Livestock, Inc. v. Furst*, 342 Ga. App. 25, 28 (2017)."

*What the real authority says.* *Disaster Services* says the opposite. In its text, which I re-verified: "Tortious interference claims, whether asserting interference with contractual relations, business relations, or potential business relations, share certain common essential elements: (1) improper action or wrongful conduct by the defendant without privilege; (2) the defendant acted purposely and with malice with the intent to injure; ...". *Valdosta Livestock v. Furst* could not be found:

- 342 Ga. App. 25 falls within *Hospital Authority of Valdosta/Lowndes County v. Fender* (342 Ga. App. 13, CL 4406052). My `analyze_citations` re-run flagged the name mismatch at similarity 0.34.
- The only cases captioned "Valdosta Livestock" are the 1962-63 E.D.N.C. and Fourth Circuit *Williams* decisions.

*How the rubric treats it.* C-020 requires the memo to state that interference with contract requires no wrongful act, and that the wrongful-act element belongs only to interference with business relations. That is the very distinction *Disaster Services* rejects. C-019 rests on the same element list.

There is a fair counterpoint. Inside the fiction, the summary-judgment order is the court's ruling in the case, and a rubric may legitimately ask a reviewer to hold opposing counsel's instructions to it. Even so, C-020 asks the memo to state the rule as Georgia law, and the order's only supporting authorities do not support it.

*Model runs and grades.*

- Both runs passed C-019 and failed C-020 under both judges.
- Opus cited "SJ Order Sec. IV.E (citing Disaster Servs. and Valdosta Livestock)" without catching either problem.
- Luna relied on the order's elements without citing cases.
- Both AI audits (GPT-6 Sol F1; Opus 5.5 O1) independently concluded that C-020 states a false Georgia rule. They relied on other Georgia lines of authority that were not independently re-verified for this report.

**C-011: Reasonable secrecy efforts (*Hoshizaki*).** The summary-judgment order's only authority for the totality-of-circumstances standard is "*Hoshizaki Am., Inc. v. Heil*, 338 Ga. App. 38, 44 (2016)."

- 338 Ga. App. 38 is *Abdalla v. Atlanta Nephrology Referral Center* (CL 4239192); I re-verified the mismatch.
- CourtListener has no case with Hoshizaki as a party, and web searches returned only corporate pages.
- The proposition itself follows from the GTSA's "reasonable under the circumstances" text.

Both runs passed C-011. **Opus carried the fabricated cite into its deliverable** as "Hoshizaki, 338 Ga. App. at 44."

**C-001 / C-002: SignalSift public-disclosure ruling (*Cochran*).** The order cites *Cochran v. Ogletree*, 244 Ga. App. 828, 833 (2000), for loss of trade-secret status on publication. That page is *Sims v. State*. The real *Cochran v. Ogletree* (244 Ga. App. 537) concerns refunds of deposits on construction contracts that were never performed, and "trade secret" returns 0 hits in it. C-002 rewards citing the order rather than this case. Both runs passed, and neither cited *Cochran*.

**C-029: Unobjectionable instructions (*Penalty Kick*, Ga. App. form).** Defense Instruction No. 15 and the summary-judgment order both cite "*Penalty Kick Mgmt. Ltd. v. Coca Cola Co.*, 318 Ga. App. 586 (2012)." That cite is *Dodson v. Walraven* (CL 7928139; I re-verified it). The real decision is 318 F.3d 1284 (11th Cir. 2003): the volume number matches, but the reporter, court and year are transposed. The plaintiff's brief in the same record cites the F.3d version correctly.

C-029 offers No. 15 as an example of an instruction that should not be objected to. Opus flagged the cite ("Cite-check Penalty Kick in all filings") and passed. Luna objected to No. 15 on substance and also passed. The Opus audit (O7) flagged the discrepancy.

**C-013: Complementary damages (*University Computing*).** The plaintiff's brief says *University Computing*, 504 F.2d at 535, permits "complementary recovery of plaintiff's losses and defendant's gains." The court instead treats them as alternatives. Plaintiff's loss is "an inappropriate measure" where the secret is not destroyed, and "the appropriate measure ... is not what plaintiff lost, but rather the benefits, profits, or advantages gained by the defendant." C-013 rests on O.C.G.A. § 10-1-763(a), which does allow non-duplicative recovery of both, so the conclusion survives without the case. Neither run cited it, and both passed.

### 3C. draft-responses-to-interrogatories

**C-012: Work-product protection for dual-purpose documents (*Cendant*).** Both the client-interview memo and the firm's discovery guidelines present *In re Cendant Corp. Sec. Litig.*, 343 F.3d 658 (3d Cir. 2003), as the source of the Third Circuit's "primary motivating purpose" test.

- *Cendant* concerns a non-testifying trial consultant and opinion work product. "Primary" returns 0 hits in the lead opinion (I re-verified this; the original agent also searched the concurrence).
- The test is in *United States v. Rockwell Int'l*, 897 F.2d at 1266: "as long as the primary motivating purpose behind the creation of the document was to aid in possible future litigation." The guidelines pair *Rockwell* with *Cendant* in a string cite, so the string cite as a whole is supportable, but *Cendant* alone is not.
- The legal conclusion is correct Third Circuit law, so an agent relying on the memo would reach the right result with the wrong citation.

Neither run cited case law, and both passed C-012. Worksheet item #19 (C-028, purchase-history figures) does not involve case law.

---

## 4. Patterns

1. **Real reporter cite, invented or swapped case name.** Several citations point to a real volume and page, but the case name belongs to no case at that location:
   - *Hollcroft & Sedgewick* points to *Ernst & Young v. Pacific Mutual* (51 S.W.3d 573).
   - *Valdosta Livestock v. Furst* points to *Hosp. Auth. of Valdosta v. Fender*.
   - *Hoshizaki v. Heil* points to *Abdalla*.
   - *FMC v. Taiwan Taiyo Yuden* (743 F.2d 1470) points to *United States v. Esle*.

   A related variant is a **real case under a garbled cite** (wrong page, reporter or court): *Cochran* (828 vs. 537), *Paramount* (791 vs. 596), *Penalty Kick* (Ga. App. vs. F.3d), *Brasby* (A.2d vs. unpublished WL), and *FMC* (Fed. Cir. vs. 2d Cir.). This is the classic profile of language-model citation generation. A citator lookup by reporter alone would "verify" most of these, and only a name check exposes them.

2. **Real case, invented quotation.** Quoted language with no counterpart in the opinion: *SIGA*, *Eagle Industries*, *Presidio*, *Excess Underwriters*, *Chapman*, *Melody Home* (the Arcadia letter's "sophisticated consumers"), *Lormand*, and *Kuhn* (pinned past its last page).

3. **Real case, inverted disposition.** The party described as losing actually won: *Chapman*, *Sharyland*, *Riverside*, *Benchmark*, *Dorsey*, *Sloane*, *Pizza Hut* (context rule), *Disaster Services* (element list), and *University Computing*.

4. **Wholly fabricated cases tailored to the fact pattern.** *Kana Software*, *Simulados* and *Precision Healthcare* each mirror the task's own contract terms: liability caps and a 30-day deemed-acceptance window. *MiMedx v. Sparks* carries a real docket number belonging to an unrelated case. *Thompson v. Pacific Envtl.* is a lower-stakes instance inside a billing narrative.

5. **Errors sit in documents agents are implicitly told to trust.** The heaviest concentrations are in:
   - a document styled as the firm's own case-law research memo (23 of 31 authorities defective)
   - a fictional federal summary-judgment order (6 of its 15 real-authority citations defective, including the four-element test at the heart of C-020)
   - a fictional TRO order (2 of 6 defective)

   Errors also appear in both sides' advocacy documents (DTPA demand and response letters, the complaint appendix, trial briefs). Real litigation documents do contain miscitations, so their presence is not by itself a defect in the environment. The rubrics, however, do not treat them as traps (point 6).

6. **The rubrics reward reproducing defective authority and do not reward catching it.**
   - C-023, C-024 and C-037 name, as model authority, cases that contradict or never discuss the required proposition.
   - C-020 requires a rule that its own cited authority refutes.
   - C-029 (jury instructions) treats an instruction resting on a broken cite as unobjectionable.
   - The verifying agents identified no criterion that credits flagging a defective authority.
   - In the clearest test (item #17, C-037), the run that caught the defects and cited the correct authority (*Abry*) was failed by both judges.

   We cannot tell from the environment whether any defect was planted deliberately. As built, though, the rubrics treat these authorities as correct.

7. **Where a rubric names an authority only for a narrow, accurate proposition, the defect is harmless to grading.** Examples: the 9(b) standard from *Benchmark* and *Dorsey*, the puffery definition from *Pizza Hut*, the express-contract bar from *Excess Underwriters* and *Fortune*, and the elements and damages limit from *McCamish* and *Sloane*. Both runs passed all of those criteria. The grading harm is concentrated in C-020, C-023, C-024 and C-037, where the named case is the support for the contested proposition itself.

8. **Model behavior.** The two runs reviewed (GPT-6 Luna xhigh; Claude Opus 5.5 low) differed sharply:
   - In the MTD task, Opus produced an explicit citation-problems table flagging most of the defective memo authorities.
   - In the jury-instructions task, Opus repeated *Hoshizaki*, *Disaster Services* and *Valdosta* through the summary-judgment order without catching them, though it did catch *Penalty Kick*.
   - Luna mostly avoided citing case law, which shielded it from repeating defective authority but also earned no credit on criteria that name cases.

   This is a two-run sample and does not support model-level generalization.

---

## 5. Limits, re-verification, and definitions

### 5.1 Claims I re-verified on CourtListener for this report

| Claim | Result |
|---|---|
| *Valdosta Livestock*, 342 Ga. App. 25 | Resolves to *Hosp. Auth. of Valdosta/Lowndes Cnty. v. Fender* (CL 4406052), with a name-mismatch warning at similarity 0.34. A caseName search returns only *Valdosta Livestock Co. v. Williams* (E.D.N.C. 1962; 4th Cir. 1963). (The original agent reported no name warning; my run did flag one. The conclusion is the same.) |
| *Disaster Services* at 740 | The "(1) improper action or wrongful conduct by the defendant without privilege" sentence covers contractual relations (CL 1388876). |
| *Kana Software*, 178 A.3d 1045 | Citation not found; caseName `(Kana AND Sealand)` returns 0. |
| *Brasby*, 947 A.2d 1042 | Citation not found. |
| *Hoshizaki*, 338 Ga. App. 38 | Resolves to *Abdalla* (CL 4239192), with a name-mismatch warning. |
| *FMC*, 743 F.2d 1470 / 730 F.2d 61 | 743 F.2d 1470 resolves to *United States v. Esle* (CL 441827). 730 F.2d 61 is *FMC v. Taiwan Tainan Giant* (2d Cir. 1984, CL 433035), containing "A trade secret once lost is, of course, lost forever." |
| *Hollcroft*, 51 S.W.3d 573 | Resolves to *Ernst & Young v. Pacific Mutual* (CL 1579057). |
| *Penalty Kick*, 318 Ga. App. 586 | Resolves to *Dodson v. Walraven* (CL 7928139), with a name-mismatch warning. |
| *SIGA* | "Integration clause" returns 0 hits in the lead opinion. |
| *Eagle Industries* | "Cannot promise" returns 0 hits (CL 2395434). |
| *Chapman* | "the rule does not apply here", plus the *LAN/STV* "contractual expectancy" sentence that the memo attributes to *Sharyland* (CL 2831423). |
| *Lormand* | Filed 2009-04-09 (CL 65339). |
| *Cendant* | "Primary" returns 0 hits in the lead opinion (lead only; the original agent also searched the concurrence). |
| *Thompson v. Pacific Envtl.* | My Washington-court search was narrower than the original agent's (caseName `Thompson AND Pacific` plus "remediation"). It returned 0, which is consistent with the original null result but does not independently replicate the original agent's full set of searches. |

Everything else in this report rests on the per-task agents' verification, which I did not repeat.

### 5.2 What could not be verified

- **"Not found" means "likely fabricated", not proven fabricated.** The seven NOT FOUND entries survived citation lookup, citation search, caseName search and (for most) full-text and web search. CourtListener does not hold every unpublished or Westlaw-only decision. Westlaw and Lexis were not searched directly.
- **Westlaw cites.** *Simulados* (2019 WL 4573218) and *MiMedx* (2020 WL 7626433) could not be checked against Westlaw. The null results rest on case-name and docket searches; *MiMedx*'s docket number belongs to *Ombonga v. Triage Consulting*.
- ***Brasby v. Morris*, 2007 WL 949485**, was confirmed only through later Delaware Superior Court opinions that cite it; its text was not read.
- ***Oregon JV LLC v. Advance Investment Corp.*** (worksheet item #4; cited in the GPT-6 Sol audit, not the environment). The June 7, 2023 order (ECF 95; 2023 WL 3886111) is not on RECAP. Its holding was confirmed through the same court's ECF 100, which quotes it ("whether an express contract existed is a matter yet to be determined"). The "pp. 17-18" pin was not checked.
- ***Hadley v. Baxendale*** (1854, Exchequer) is not hosted on CourtListener. It was verified through Washington Supreme Court opinions that apply it (e.g., *Gaglidari v. Denny's*, 117 Wn.2d 426).
- **Pins and quotations not text-tested:**
  - Feld's A.2d pin (CourtListener carries only Pa. pagination)
  - the *Daubert* 596 quotation (confirmed only through *Quiet Technology*'s quotation of it)
  - *Dorsey* at 340 (partially searched)
  - *Presidio* pins 679-80
  - *Iqbal*'s "reasonable expectation" attribution (that language is *Twombly* at 556)
  - the parentheticals for *Italian Cowboy*, *Formosa*, *Heldenfels* and *Tony Gullo*
  - standard propositions for *Anderson*, *Celotex*, *Matsushita*, *Tolan*, *Erie*, *Carden*, *Arbaugh*, *Hertz*, *St. Paul Mercury*, *De Aguilar*, *Strawbridge*, *Nixon*, *Conley* and *PepsiCo* (existence and name confirmed; text not re-read)
- **Method limits.** Literal phrase searches depend on CourtListener's text and OCR. A 0-hit result is strong evidence that a quotation is absent, but not a proof, and star-page pins depend on CourtListener's pagination. One per-task agent's advisor call was rate-limited.
- **Out of scope:** statutes, rules, the Restatement, pattern jury instructions and ethics opinions. Citations in model-run deliverables and AI audit reports were spot-checked only where noted. For example, Opus 5.5's five Ninth Circuit and Supreme Court cites in compare-document-production, *In re Grand Jury*, 23 F.4th 1088, *Nationwide v. Home Ins.*, 278 F.3d 621, and *Town of Alma* and *BRW* all exist. They were not systematically audited.

### 5.3 "Verified" is not "every pin checked"

The per-task agents applied this rule:

- **Mischaracterized:** the environment attributes a quotation with no counterpart in the opinion, or a holding or facts the opinion contradicts.
- **Verified with a note:** the quoted words are real language from another authority, or a close paraphrase of the cited page, and the proposition is supported.

Under that rule, 16 of the 57 verified instances carry a noted defect:

- ***Twombly***: "sheer possibility" is *Iqbal* at 678.
- ***Iqbal***: carries *Twombly* language.
- ***Castrol***: the "blustering" definition is McCarthy's, quoted in *Pizza Hut*; *Castrol* held Pennzoil's claims were *not* puffery.
- ***Fortune***: a close paraphrase rather than a quotation.
- ***Speaks v. Kruse***: no "burden" language.
- ***Jazzabi***: the language is at 984-85, not 986.
- ***Alabama Aircraft***: a district court decision called "The Eleventh Circuit", with the pin at 741 rather than about 745-46.
- ***Heller***: the pin is slightly early.
- ***Mancia***: a D. Md. case framed as Third Circuit or W.D. Pa. authority.
- ***Bristol-Myers Squibb***: grouped under "stream of commerce", a phrase the opinion never uses.
- ***Carden***: C-002's title calls the case "Carden v. Arkoma LLC" (Arkoma was a limited partnership).
- ***Amstadt***, ***PPG*** (Arcadia letter), ***Doe v. Boys Clubs***, ***Bartush***: loose parentheticals.
- ***Matsushita***: a loose "see" cite for cross-motions.

Fit caveats that are not defects:

- *Upjohn* and *Zubulake* are federal civil doctrines applied to an Ohio state matter and a grand-jury matter.
- *Nicastro* is a plurality opinion.
- *Formosa* fits fraud committed during performance, rather than inducement, only imperfectly.

### 5.4 Fictional-by-design material is not hallucination

The 48 fictional-by-design items are each task's own captioned matter, in-universe court orders (summary-judgment, TRO, sanctions, scheduling and case-management orders), firm matter numbers, an EEOC charge number, and expert-CV engagements (15 in the motion-in-limine task alone). None is offered as precedent, and none is counted as a problem.

Two edge cases:

- The draft-case-assessment caption's docket number, 3:24-cv-00891 (D. Or.), collides with an unrelated real case, *Carlton v. Allstate*. That is a coincidence, not hallucination.
- The in-universe scheduling order in the MTD task cites "W.D. Tex. Standing Order 2019-03", which the Opus run could not locate. It is a citation to a purportedly real order, but not case law, so it is not counted.

The line drawn throughout: an invented matter used as the scenario is fiction by design, while an invented or garbled citation presented as real precedent is a hallucinated authority, whether it appears in a fictional document or not.

### 5.5 Non-case-law observations (excluded from all counts)

- **draft-conflict-check-memorandum** (items #5, #6 do not depend on these):
  - C-022 mislabels Illinois Rule 1.8(i) as the "related persons" rule.
  - C-037 cites a nonexistent "Illinois Rule 1.10(a)(2)"; lateral screening is Illinois Rule 1.10(e).
  - C-038 credits ABA-only former-client notice.
  - Both AI audits flagged these.
- **draft-counterclaim** (items #7, #8). The environment calls U.S. Patent No. 11,234,567 Vantage's SensorCore patent, issued January 10, 2023. Google Patents shows that number as a SharkNinja vacuum-tool patent granted February 1, 2022 (one source; not confirmed with USPTO). C-045 and C-046 require pleading that number.
- **draft-motion-to-dismiss-brief.** Tex. Bus. & Com. Code § 17.49(f) is misstated in the memo, both DTPA letters, and criteria C-025 and C-089. The $500K exemption is § 17.49(g), and the $25M asset test is in § 17.45(4).
- **identify-issues-in-matter-budget-proposal.** "O.C.G.A. § 10-1-761 et seq." should begin at § 10-1-760 (minor).
- **review-counterpartys-proposed-jury-instructions.** C-027 names Eleventh Circuit Pattern Instruction 3.5 as the expert instruction. The Opus audit reports that the expert instructions are 3.6.1/3.6.2 (not independently checked).

---

## Appendix: per-task counts

"Citations" are citation instances to purported real judicial authority in the environment (supplied documents plus `task.json`). Worksheet items are the sampled criteria in each task.

| Task | Worksheet item(s) | Docs | Citations | Verified | Problems | Fictional by design |
|---|---|---|---|---|---|---|
| assess-reasonableness-of-staffing-levels-on-litigation-invoice | #1 C-049 | 5 | 1 | 1 | 0 | 1 |
| categorize-document-production-set-by-relevance-and-privilege | #2 C-012 | 25 | 1 | 1 | 0 | 1 |
| compare-document-production-against-discovery-requests | #3 C-029 | 8 | 0 | 0 | 0 | 1 |
| draft-case-assessment-memorandum | #4 C-025 | 8 | 0 | 0 | 0 | 1 |
| draft-conflict-check-memorandum | #5 C-030, #6 C-049 | 8 | 0 | 0 | 0 | 5 |
| draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement | #7 C-045, #8 C-046 | 8 | 0 | 0 | 0 | 1 |
| draft-defective-industrial-equipment-product-liability | #9 C-003, #10 C-026 | 9 | 2 | 2 | 0 | 0 |
| draft-discovery-plan-memorandum | #11 C-036 | 10 | 0 | 0 | 0 | 2 |
| draft-federal-complaint-drafting | #12 C-025 | 8 | 2 | 2 | 0 | 1 |
| draft-interrogatories | #13 C-008, #14 C-026 | 9 | 6 | 4 | 2 | 1 |
| draft-litigation-discovery-responses | #15 C-028 | 7 | 1 | 1 | 0 | 2 |
| draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence | #16 C-009 | 8 | 2 | 2 | 0 | 15 |
| draft-motion-to-dismiss-brief | #17 C-037, #18 C-045 | 24 | 53 (49 unique) | 25 | 28 | 5 |
| draft-responses-to-interrogatories | #19 C-028 | 10 | 9 (8 unique) | 5 | 4 | 1 |
| extract-key-obligations-from-litigation-hold-and-document-preservation-notice | #20 C-002 | 5 | 1 | 1 | 0 | 1 |
| identify-excessive-or-duplicative-research-charges-in-litigation-invoice | #21 C-013 | 6 | 2 | 1 | 1 | 2 |
| identify-issues-in-matter-budget-proposal | #22 C-029 | 5 | 0 | 0 | 0 | 1 |
| review-counterpartys-proposed-jury-instructions | #23 C-020 | 6 | 21 | 11 | 10 | 6 |
| review-litigation-invoice-against-outside-counsel-billing-guidelines | #24 C-024, #25 C-042 | 5 | 1 | 1 | 0 | 1 |
| **Total** | 25 items | **174** (+19 `task.json`) | **102** (97 unique within tasks; 91 across tasks) | **57** | **45** | **48** |