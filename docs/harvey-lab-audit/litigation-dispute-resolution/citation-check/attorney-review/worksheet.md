# Attorney review of sampled citation-check findings: worksheet

Review in order, following the [protocol](README.md). Fill in the three fields under each entry; leave everything else as drawn.

## 1. draft-jury-instructions — citation 48 (first ten)

- **Document:** [partial-summary-judgment-order.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/documents/partial-summary-judgment-order.docx), IV.D Count IV, para 3
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-jury-instructions/task.json)
- **Authority as written:** Karnes v. Doctors Hospital, 51 Ohio St.3d 139, 142, 555 N.E.2d 280 (1990) (pin 142)
- **Cited for:** General disclaimer may be insufficient to negate specific representations regarding termination procedures
- **Context:** (holding that a general disclaimer may be insufficient to negate specific representations regarding termination procedures)
- **AI finding:** MISCHARACTERIZED
- **AI explanation:** The finding holds. I read the full per curiam opinion on CourtListener (6762446). Karnes holds the opposite of the parenthetical: "This construction of the legal effect of the manual is belied by its clear language to the contrary. The manual specifically disclaims any intent to create a contractual relationship ... Accordingly, the status of appellant cannot be characterized as that of a contract employee." Page 142 only restates the Mers promissory-estoppel test and then finds no detrimental reliance, because the appellant "has failed to identify what provisions of the handbook were relied upon by her." The opinion never says a general disclaimer may be insufficient to negate specific termination-procedure representations. It also does not hold that the question is one for the factfinder, which the order elsewhere cites it for. The citation itself (51 Ohio St.3d 139, 555 N.E.2d 280 (1990)) is correct.
- **What the source says (AI excerpt):** “"This construction of the legal effect of the manual is belied by its clear language to the contrary. The manual specifically disclaims any intent to create a contractual relationship between employer and employee ... Accordingly, the status of appellant cannot be characterized as that of a contract employee."”
- **Sources the AI read:** https://www.courtlistener.com/opinion/6870499/karnes-v-doctors-hospital/

<details><summary>Passage in the document</summary>

> …erstanding that the employer would follow the identified procedures before taking adverse action. The tension between the Handbook's at-will disclaimer (page 3) and the progressive-discipline provision (pages 27–28) is at the heart of this claim. Ohio courts have grappled with this precise tension. A general at-will disclaimer does not necessarily negate specific procedural commitments made elsewhere in the handbook. See Karnes v. Doctors Hospital, 51 Ohio St.3d 139, 142, 555 N.E.2d 280 (1990) (holding that a general disclaimer may be insufficient to negate specific representations regarding termination procedures); Wing v. Anchor Media, Ltd. of Texas, 59 Ohio St.3d 108, 111, 570 N.E.2d 1095 (1991) (similar). The question is whether the progressive-discipline language — "Employees will be given progressive discipline consisting of (1) verbal warning, (2) written warning, (3) final written warning, and (4) termination, except in cases of gross misconduct" (emphasis added) — is sufficiently specific and definite to create an implied contractual obligation, notwithstanding the at-will disclaimer. This is a question that Ohio courts have generally held to be one for the factfinder. See Karnes, 51 Ohio St.3d at 142; Wing, 59 Ohio St.3d at 111. Among the considerati…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: Karnes)
- **AI's reading of the rubric:** SJ order cites Karnes for the opposite of its holding. The finding shows the case does not support the order's proposition, but does not show the proposition (a disclaimer does not always negate specific handbook commitments; jury question) wrong under Ohio law, and the SJ order makes it law of the case; C-018/C-019 adopt that proposition without citing this case, so this is not counted as rubric reliance. No criterion asks the model to check the order's authorities.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 2. review-counterpartys-proposed-jury-instructions — citation 77 (first ten)

- **Document:** [defense-proposed-jury-instructions.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/documents/defense-proposed-jury-instructions.docx), Instruction No. 6
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json)
- **Authority as written:** Eleventh Circuit Pattern Jury Instruction 1.3
- **Cited for:** Parties equal before the law
- **Context:** Authority: Eleventh Circuit Pattern Jury Instruction 1.3.
- **AI finding:** WRONG_CITATION_REAL_CASE
- **AI explanation:** Confirmed. In the April 2024 edition, Instruction 1.3 is "Official English Translation/Interpretation" ("You may hear or see languages other than English during this trial... you must accept the English [interpretation/translation] provided"). It has nothing on parties being equal before the law. That principle appears in Instruction 3.2.2 (Duty to Follow Instructions - Corporate Party Involved): "A corporation and all other persons stand equal before the law and must be dealt with as equals in a court of justice." That supports Proposed Instruction No. 6. The 2005 edition has no instruction 1.3 matching either; its corporate-party instruction is Basic 2.2. MISCHARACTERIZED would also be defensible, but because the right instruction exists under a different number, a wrong citation is the better fit. Correct cite: 11th Cir. Civ. PJI 3.2.2.
- **What the source says (AI excerpt):** “1.3 Official English Translation/Interpretation. You may hear or see languages other than English during this trial. You must consider evidence provided through only the official court [interpreters/translators]. [Compare 3.2.2:] A corporation and all other persons stand equal before the law and must be dealt with as equals in a court of justice.”
- **AI's correct citation:** Eleventh Circuit Civil Pattern Jury Instruction 3.2.2 (The Duty to Follow Instructions – Corporate Party Involved)
- **Sources the AI read:** https://www.ca11.uscourts.gov/sites/default/files/courtdocs/clk/FormCivilPatternJuryInstructionsRevisedAPR2024.pdf · https://www.rid.uscourts.gov/sites/rid/files/documents/juryinstructions/otherPJI/11th%20Circuit%20Pattern%20Civil%20Jury%20Instructions.pdf

<details><summary>Passage in the document</summary>

> …ter or lesser weight to the claims or defenses of any party because of whether the party is a corporation or an individual. Oakvale Technologies, Inc. and Axial Systems Corp. are each entitled to the same fair and unprejudiced treatment as an individual would receive. Similarly, Dr. Nolan Voss, as an individual, is entitled to the same fair and unprejudiced treatment as any corporate party. You should decide this case based on the evidence and the law, without regard to the nature of any party. Authority: Eleventh Circuit Pattern Jury Instruction 1.3. Proposed Instruction No. 7 — Consideration of Multiple Defendants In this case, there are two defendants: Dr. Nolan Voss and Axial Systems Corp. You must consider the evidence and the claims against each defendant separately. Each defendant is entitled to have your individual judgment applied to the evidence concerning that defendant. The fact that you may find for or against one defendant should not control or influence your verdict as to the other defendant. Each claim against each defendant must be evaluated independently, based upon the evidence and the law applicable to that claim and that defendant. Authority: Eleventh Circuit Pattern Jury Instruction 1.4. Proposed Instruction No. 8 —…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: 1.3)
- **AI's reading of the rubric:** No criterion addresses Instruction 6 or its pattern-number cite.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 3. review-counterpartys-proposed-jury-instructions — citation 103 (first ten)

- **Document:** [defense-proposed-jury-instructions.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/documents/defense-proposed-jury-instructions.docx), Instruction No. 28
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json)
- **Authority as written:** Eleventh Circuit Pattern Jury Instruction 4.12
- **Cited for:** Causation
- **Context:** Authority: O.C.G.A. § 51-12-9; Eleventh Circuit Pattern Jury Instruction 4.12.
- **AI finding:** MISCHARACTERIZED
- **AI explanation:** Confirmed. I extracted the text of the Eleventh Circuit Civil Pattern Jury Instructions in two editions: the current compilation (rev. Apr. 2024) and the 2013 edition. In both, 4.12 is the ADA instruction. The 2024 table of contents reads '4.12 Americans with Disabilities Act - Reasonable Accommodation Claim - 42 U.S.C. §§ 12101-12117', and the 2013 TOC also lists '4.12 Americans with Disabilities Act:—Reasonable—'. Neither is a general causation or proximate-cause instruction. The pattern compilation uses 'proximate cause' only inside claim-specific instructions, such as the employment-claim and securities-fraud elements. The pattern does not supply Instruction 28's general proximate-cause definition. That definition tracks Georgia law, and the instruction also cites O.C.G.A. § 51-12-9 for it. I did not check the pre-2013 (2005) edition.
- **What the source says (AI excerpt):** “4.12 Americans with Disabilities Act: – Reasonable Accommodation Claim – 42 U.S.C. §§ 12101-12117 In this case, [name of plaintiff] claims that [name of defendant] discriminated against [name of plaintiff] because of [his/her] disability by failing to provide a reasonable accommodation”
- **Sources the AI read:** https://www.ca11.uscourts.gov/sites/default/files/courtdocs/clk/FormCivilPatternJuryInstructionsRevisedAPR2024.pdf · https://www.ca11.uscourts.gov/sites/default/files/courtdocs/clk/FormCivilPatternJuryInstruction2013.pdf

<details><summary>Passage in the document</summary>

> …continuous sequence, produces the injury, and without which the injury would not have occurred. There may be more than one proximate cause of a particular injury. You should consider whether the plaintiff has established a sufficient connection between the defendants' alleged conduct and the damages the plaintiff claims to have suffered. If the plaintiff's injuries would have occurred regardless of the defendants' conduct, then the defendants' conduct is not a proximate cause of those injuries. Authority: O.C.G.A. § 51-12-9; Eleventh Circuit Pattern Jury Instruction 4.12. Proposed Instruction No. 29 — Plaintiff's Failure to Enforce Contractual Rights / Apportionment In determining damages, you should consider whether Oakvale's own failure to enforce its contractual rights in a timely manner contributed to its claimed losses, and you should reduce any damages award proportionally. If you find that Oakvale Technologies, Inc. delayed in taking action to protect its alleged trade secrets or enforce the terms of the Employment Agreement, you should take this delay into account when determining the amount of any damages. The law requires that a party exercise reasonable diligence in protecting its own interests. To the extent you find that Oakvale Technologies, In…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: 4.12)
- **AI's reading of the rubric:** No criterion addresses Instruction 28 or its cite to pattern 4.12 (an ADA instruction).

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 4. draft-motion-to-dismiss-brief — citation 82 (first ten)

- **Document:** [key-case-law-compilation-defense-research-memo.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/documents/key-case-law-compilation-defense-research-memo.docx), Section V.A (Riverside National Bank v. Lewis)
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json)
- **Authority as written:** Riverside National Bank v. Lewis, 603 S.W.2d 169 (Tex. 1980) (pin 173)
- **Cited for:** Broad DTPA consumer definition; nexus between deceptive act and goods/services
- **Quoted as:** “nexus”
- **Context:** The court held that the Lewises qualified as consumers because they sought the "services" of the bank (loan services). Id. at 173.
- **AI finding:** MISCHARACTERIZED
- **AI explanation:** The finding holds. Riverside Nat'l Bank v. Lewis, 603 S.W.2d 169, has the headings "Lewis did not seek or acquire any 'goods'" and "Lewis did not seek or acquire any 'services' in his transaction with Riverside Bank." It holds "Lewis' attempt to acquire money, or the use of money, was not an attempt to acquire services" (174-75). It also rejects the argument that collateral loan-processing activities were services. At 173 it holds only that a private plaintiff "must be a consumer, as defined in section 17.45(4)." A search for "nexus" returned 0 matches. The definition the opinion quotes is the 1973 text ("an individual who seeks or acquires by purchase or lease, any goods or services"), not the later amended text the memo gives. The memo reverses the holding.
- **What the source says (AI excerpt):** “Since we believe that Mr. Lewis was not a "consumer" in the instant transaction, we hold that the trial court correctly denied recovery under the DTPA.”
- **Sources the AI read:** https://www.courtlistener.com/opinion/1624043/riverside-national-bank-v-lewis/

<details><summary>Passage in the document</summary>

> …nk argued that the DTPA did not apply to the transaction because the Lewises were not "consumers" within the meaning of the statute. Holding: The Texas Supreme Court held that the DTPA defines "consumer" broadly as "an individual, partnership, corporation, this state, or a subdivision or agency of this state who seeks or acquires by purchase or lease, any goods or services." Tex. Bus. & Com. Code § 17.45(4). To qualify as a "consumer," a plaintiff must have sought or acquired goods or services. The court held that the Lewises qualified as consumers because they sought the "services" of the bank (loan services). Id. at 173. However, the court emphasized that the consumer must demonstrate a "nexus" between the alleged deceptive act and the goods or services sought or acquired. Key Principles: 1. "Consumer" status under the DTPA requires that the plaintiff sought or acquired "goods or services." 2. There must be a nexus between the goods or services and the alleged deceptive trade practice. 3. The DTPA is a remedial statute construed liberally, but it has statutory exemptions that courts must honor. Relevance to Our Case: While Riverside National Bank establishes the broad framework for consumer status, the critical issue for Meridian is whether the § 17.49(f) ex…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: Riverside, Lewis)
- **AI's reading of the rubric:** No criterion names Riverside National Bank or asks the model to verify the memo's DTPA consumer-status authority. No instruction or criterion asks the model to check the research memo's or the parties' authorities; the 'internal memo flagging threshold issues' instruction is aimed at jurisdiction (C-013–C-017, C-064–C-066).

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 5. assess-settlement-value-range — citation 42 (first ten)

- **Document:** [defense-mediation-brief.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-settlement-value-range/documents/defense-mediation-brief.docx), III.B Apex's Modification Was the Proximate Cause (para 3)
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-settlement-value-range/task.json)
- **Authority as written:** O.R.C. § 2307.76(A)(2) (pin (A)(2))
- **Cited for:** Manufacturer defense where product altered or modified after leaving manufacturer's control and alteration was a proximate cause of harm
- **Context:** See O.R.C. § 2307.76(A)(2) (providing a defense where the product was altered or modified after it left the manufacturer's control, and such alteration or modification was a proximate cause of the harm).
- **AI finding:** MISCHARACTERIZED
- **AI explanation:** The finding holds. I read the official text of R.C. 2307.76. Division (A)(2) defines a defect for 'inadequate post-marketing warning or instruction': the manufacturer 'knew or, in the exercise of reasonable care, should have known about a risk' and 'failed to provide the post-marketing warning or instruction that a manufacturer exercising reasonable care would have provided.' It says nothing about alteration or modification after the product left the manufacturer's control, and it creates no proximate-cause defense of that kind. Whatever common-law basis an alteration defense may have, the cited division describes a different rule, so it is cited for a rule it does not contain.
- **What the source says (AI excerpt):** “(2) It is defective due to inadequate post-marketing warning or instruction if, at a relevant time after it left the control of its manufacturer, both of the following applied: (a) The manufacturer knew or ... should have known about a risk ...”
- **Sources the AI read:** https://codes.ohio.gov/ohio-revised-code/section-2307.76

<details><summary>Passage in the document</summary>

> …general-purpose aftermarket product using generic instructions. This conduct represents a textbook example of an independent, intervening modification that severs the chain of causation between the original manufacturer and the ultimate injury. Under Ohio law, a product manufacturer is not liable for injuries caused by substantial alterations or modifications made to its product after it leaves the manufacturer's control, where such modifications are a proximate cause of the plaintiff's injury. See O.R.C. § 2307.76(A)(2) (providing a defense where the product was altered or modified after it left the manufacturer's control, and such alteration or modification was a proximate cause of the harm). Apex's modification was not merely a proximate cause — it was the proximate cause. Without the 4.5-inch gap, Holt's hand could not have entered the point of operation. This is not a matter of expert opinion or competing theories; it is a matter of physical reality. Plaintiff's expert, Dr. Vasquez, offers a counterargument: that the alleged re-cycling defect in the GP-7500 would have posed a hazard even with the original Greenfield guard in place, because the original guard was purportedly designed to protect during the downstroke only and did not account for an unexpect…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: 2307.76(A)(2))
- **AI's reading of the rubric:** R.C. 2307.76(A)(2) cited for a modification defense; C-013/C-014 treat Apex's modification as a comparative-fault fact without citing or testing this statute.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 6. draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence — citation 80 (first ten)

- **Document:** [osha-citation.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/documents/osha-citation.docx), Posting Requirement
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/task.json)
- **Authority as written:** Occupational Safety and Health Act of 1970, Section 17(l), 29 U.S.C. 666(l), Section 17(l) of the Occupational Safety and Health Act of 1970, 29 U.S.C. § 666(l)
- **Cited for:** Additional citations and penalties for failure to comply with posting requirement
- **Context:** may result in the issuance of additional citations and penalties under Section 17(l) of the Occupational Safety and Health Act of 1970, 29 U.S.C. § 666(l).
- **AI finding:** WRONG_CITATION_REAL_CASE
- **AI explanation:** Finding holds. 29 U.S.C. § 666(l), OSH Act § 17(l), reads: '(l) Procedure for payment of civil penalties. Civil penalties owed under this chapter shall be paid to the Secretary for deposit into the Treasury ... and may be recovered in a civil action ...' The penalty for violating a posting requirement is in § 666(i), OSH Act § 17(i): '(i) Violation of posting requirements. Any employer who violates any of the posting requirements, as prescribed under the provisions of this chapter, shall be assessed a civil penalty of up to $7,000 for each violation.' The statute is right and only the subsection letter is wrong ((l) for (i)), all within the same section. For that reason I treat it as a garbled citation rather than a mischaracterized authority.
- **What the source says (AI excerpt):** “(i) Violation of posting requirements: Any employer who violates any of the posting requirements, as prescribed under the provisions of this chapter, shall be assessed a civil penalty of up to $7,000 for each violation. ... (l) Procedure for payment of civil penalties: Civil penalties owed under this chapter shall be paid to the Secretary for deposit into the Treasury”
- **AI's correct citation:** Section 17(i) of the Occupational Safety and Health Act of 1970, 29 U.S.C. § 666(i)
- **Sources the AI read:** https://www.law.cornell.edu/uscode/text/29/666

<details><summary>Passage in the document</summary>

> …G REQUIREMENT</u> The employer is required to post a copy of this Citation and Notification of Penalty, or the pages of the citation relevant to each violation, at or near the location of each violation referred to herein. This citation must be posted in a prominent location where it is readily observable by all affected employees. The citation must remain posted for a period of 3 working days or until the violation is abated, whichever is longer. Failure to comply with this posting requirement may result in the issuance of additional citations and penalties under Section 17(l) of the Occupational Safety and Health Act of 1970, 29 U.S.C. § 666(l). U.S. DEPARTMENT OF LABOR OCCUPATIONAL SAFETY AND HEALTH ADMINISTRATION PORTLAND AREA OFFICE By: Raymond T. Castillo Area Director OSHA Portland Area Office 620 SW Main Street, Suite 450 Portland, OR 97205 Telephone: (503) 555-0194 Date: April 10, 2023 <u>ABATEMENT CERTIFICATION</u> The employer is required to submit written certification of abatement to the Area Director at the above address by the abatement date of May 12, 2023. The certification must include documentation of all corrective actions taken, including but not limited to: evidence of exhaust fan motor repair or replacement at Blending Station No. 3; evi…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: 17(l), 666(l))
- **AI's reading of the rubric:** Wrong OSH Act subsection for the posting-penalty notice; no criterion reaches it.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 7. draft-opposition-to-motion-to-dismiss — citation 78 (first ten)

- **Document:** [defendants-mtd-memorandum.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/documents/defendants-mtd-memorandum.docx), Table of Authorities, Cases (Deming)
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json)
- **Authority as written:** Deming v. Nationwide Mut. Ins. Co., 279 Conn. 745 (2006)
- **Cited for:** Severability and reformation of restrictive covenants (TOA entry)
- **Context:** *Deming v. Nationwide Mut. Ins. Co.*, 279 Conn. 745 (2006) | 13
- **AI finding:** MISCHARACTERIZED
- **AI explanation:** The citation form checks out: Deming v. Nationwide Mutual Insurance, 279 Conn. 745, 905 A.2d 623 (Sept. 5, 2006). The memo cites it at 763 for having 'acknowledged the tension between contractual severability provisions and the policy against enforcing unreasonable restraints'. Page *763 is actually a survey of majority and minority views on whether forfeiture-for-competition clauses are restraints of trade: 'A significant minority of jurisdictions, however, have adopted a different position. They hold that the threat of economic loss to an employee should he engage in business competition is a restraint of trade.' Severability comes up only in footnotes. N.16: 'the trial court declined to consider subsection (f) (3) ... on the ground that the subsections were severable ... Although we do not review this conclusion'. N.21: 'we need not address the plaintiffs' challenge as to whether the trial court improperly applied the "blue pencil" rule'. The court decided that the forfeiture clause must pass a reasonableness test. It did not decide anything about severability or reformation, so the proposition is not its holding.
- **What the source says (AI excerpt):** “In light of our conclusion as to the validity of paragraph 11 (f), we need not address the plaintiffs' challenge as to whether the trial court improperly applied the "blue pencil" rule when concluding that the separate conditions of the forfeiture provision could be severed when assessing reasonableness.”
- **AI's correct citation:** Deming v. Nationwide Mutual Insurance Co., 279 Conn. 745, 905 A.2d 623 (2006) (citation form is accurate; the blue-pencil discussion is dicta at 769-70 n.21)
- **Sources the AI read:** https://www.courtlistener.com/opinion/2193195/deming-v-nationwide-mutual-insurance/

<details><summary>Passage in the document</summary>

> …l Partners LLC Press Release (February 3, 2025) | 29 | TABLE OF AUTHORITIES Cases | | Page(s) | |-----------------------------------------------------------------------------------------------------------|-------------| | Ashcroft v. Iqbal, 556 U.S. 662 (2009) | 8, 9, 15 | | Bell Atl. Corp. v. Twombly, 550 U.S. 544 (2007) | 8, 9, 15 | | Branson Ultrasonics Corp. v. Stratman, 921 F. Supp. 2d 46 (D. Conn. 2013) | 10, 11 | | Bridgeport Harbor Place, Inc. v. Ganim, 303 Conn. 205 (2011) | 20, 21 | | Deming v. Nationwide Mut. Ins. Co., 279 Conn. 745 (2006) | 13 | | Elm City Cheese Co. v. Federico, 251 Conn. 59 (1999) | 23 | | Emlee Equip. Leasing Corp. v. Waterbury Transmission, Inc., 31 Conn. App. 455 (1993) | 11 | | ExcelAire, LLC v. Garaventa, No. 3:17-cv-01308, 2018 WL 1136583 (D. Conn. Mar. 2, 2018) | 10, 14 | | Hi-Q Personnel, Inc. v. Manning, 11 Conn. Supp. 436 (1943) | 9, 10 | | InVivo Therapeutics Holdings Corp. v. Esse, 83 F. Supp. 3d 330 (D. Mass. 2015) | 17 | | Iqbal v. Hasty, 490 F.3d 143 (2d Cir. 2007) | 8 | | Lumen Sols. Holdings, Inc. v. Kraska, No. 3:20-cv-01378, 2021 WL 517488 (D. Conn. Feb. 11, 2021) | 16 | | MacDermid, Inc. v. Deiter, 702 F.3d 725 (2d Cir. 2012) | 17 | | New England Overall Co. v. Woltmann, 166 Conn. 352 (1974)…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** C-011 (searched for: Deming, Nationwide)
- **AI's reading of the rubric:** No instruction or criterion asks the model to identify, flag, correct, or avoid this authority or citation errors in this document. TOA entry for Deming. C-011 does reward citing Deming for reformation, an unsupported proposition recorded separately at ref 146.

<details><summary>Text of those criteria</summary>

> **C-011. ISSUE_001 — Citation to CT reformation case law** PASS if the brief cites Connecticut case law supporting reformation of restrictive covenants (e.g., Deming v. Nationwide Mutual Insurance Co., Robert S. Weiss & Associates v. Wiederlight, or other relevant Connecticut authority on the reasonable modification standard). FAIL if no Connecticut case law on reformation or blue-penciling of non-competes is cited.

</details>

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 8. draft-opposition-to-motion-to-dismiss — citation 86 (first ten)

- **Document:** [defendants-mtd-memorandum.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/documents/defendants-mtd-memorandum.docx), Table of Authorities, Cases (MacDermid)
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json)
- **Authority as written:** MacDermid, Inc. v. Deiter, 702 F.3d 725 (2d Cir. 2012)
- **Cited for:** Trade secret specificity (TOA entry)
- **Context:** *MacDermid, Inc. v. Deiter*, 702 F.3d 725 (2d Cir. 2012) | 17
- **AI finding:** MISCHARACTERIZED
- **AI explanation:** The finding holds. MacDermid, Inc. v. Deiter, 702 F.3d 725 (2d Cir. Dec. 26, 2012), is real and correctly cited (CourtListener cluster 814269). It does not address how specifically a plaintiff must identify trade secrets. A text search of the opinion finds no occurrence of 'specificity', so the memo's quoted phrase 'reasonable specificity' (body, at 729-30) does not appear. 'Trade secret' appears only twice, both times describing the claims or the jurisdictional facts: 'alleging unauthorized access and misuse of a computer system and misappropriation of trade secrets in violation of Conn. Gen. Stat. 53a-251 and 35-51', and 'the storage of confidential, proprietary information and trade secrets in Waterbury, Connecticut'. The decision concerns personal jurisdiction under the Connecticut long-arm statute.
- **What the source says (AI excerpt):** “"We hold that, consistent with due process, the Connecticut statute authorizes jurisdiction, and we reverse."”
- **Sources the AI read:** https://www.courtlistener.com/opinion/814269/macdermid-inc-v-deiter/

<details><summary>Passage in the document</summary>

> … Leasing Corp. v. Waterbury Transmission, Inc., 31 Conn. App. 455 (1993) | 11 | | ExcelAire, LLC v. Garaventa, No. 3:17-cv-01308, 2018 WL 1136583 (D. Conn. Mar. 2, 2018) | 10, 14 | | Hi-Q Personnel, Inc. v. Manning, 11 Conn. Supp. 436 (1943) | 9, 10 | | InVivo Therapeutics Holdings Corp. v. Esse, 83 F. Supp. 3d 330 (D. Mass. 2015) | 17 | | Iqbal v. Hasty, 490 F.3d 143 (2d Cir. 2007) | 8 | | Lumen Sols. Holdings, Inc. v. Kraska, No. 3:20-cv-01378, 2021 WL 517488 (D. Conn. Feb. 11, 2021) | 16 | | MacDermid, Inc. v. Deiter, 702 F.3d 725 (2d Cir. 2012) | 17 | | New England Overall Co. v. Woltmann, 166 Conn. 352 (1974) | 9, 10 | | Premiere Digital Access, Inc. v. Cent. Tel. Co., 360 F. Supp. 2d 588 (S.D.N.Y. 2005) | 25 | | Robert S. Weiss & Assocs., Inc. v. Wiederlight, 208 Conn. 525 (1988) | 9, 13 | | Scott v. Gen. Iron & Welding Co., 171 Conn. 132 (1976) | 9 | | Torrington Creamery, Inc. v. Davenport, 126 Conn. 515 (1940) | 11 | | Turbine Powered Mach., Inc. v. Bonfiglio, No. 3:18-cv-01441, 2019 WL 2147095 (D. Conn. May 16, 2019) | 22 | | United Rentals, Inc. v. Pruett, 296 F. Supp. 2d 220 (D. Conn. 2003) | 23, 24 | | Zep Solar, Inc. v. Westinghouse Solar, Inc., No. 11-cv-06493, 2012 WL 3527849 (N.D. Cal. Aug. 14, 2012) | 19 | Statutes | | Pa…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: MacDermid, Deiter)
- **AI's reading of the rubric:** No instruction or criterion asks the model to identify, flag, correct, or avoid this authority or citation errors in this document; TOA entry.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 9. draft-responses-to-interrogatories — citation 126 (first ten)

- **Document:** [case-management-order.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-responses-to-interrogatories/documents/case-management-order.docx), Section 4(e), Discovery Disputes (line 50)
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-responses-to-interrogatories/task.json)
- **Authority as written:** W.D. Pa. Local Rule 37.1, Local Rule 37.1 of the Western District of Pennsylvania
- **Cited for:** Meet-and-confer requirement before discovery motion
- **Context:** as required by Fed. R. Civ. P. 37(a)(1) and Local Rule 37.1 of the Western District of Pennsylvania.
- **AI finding:** MISCHARACTERIZED
- **AI explanation:** I extracted the text of the W.D. Pa. Local Rules (effective Nov. 1, 2016; still the version the court's local-rules page lists). LCvR 37.1 reads in full: 'All discovery motions shall be referred to the member of the Court to whom the case was assigned for disposition, except in cases where such matters may be required to be submitted to the emergency or miscellaneous judge...'. LCvR 37.2 requires only a 'verbatim recitation of each interrogatory, request, answer, response, and objection which is the subject of the motion.' Searching the whole manual for 'confer' and 'good faith' turned up conferral duties only for scheduling-order modifications (LCvR 16.1.B.5), pretrial matters, and the Rule 26(f)/ESI meet-and-confer (LCvR 26.2.D). No local rule requires conferring before a discovery motion; that requirement comes from Fed. R. Civ. P. 37(a)(1) alone.
- **What the source says (AI excerpt):** “"LCvR 37.1 REFERRAL OF DISCOVERY MOTIONS BY CLERK OF COURT. All discovery motions shall be referred to the member of the Court to whom the case was assigned for disposition, except in cases where such matters may be required to be submitted to the emergency or miscellaneous judge, or the judge to whom matters may be temporarily referred by the judge to whom the case was assigned."”
- **AI's correct citation:** Fed. R. Civ. P. 37(a)(1) alone supplies the conferral requirement; no W.D. Pa. local rule requires conferral before a discovery motion. LCvR 37.1 is 'Referral of Discovery Motions by Clerk of Court' and LCvR 37.2 is 'Form of Discovery Motions.'
- **Sources the AI read:** https://www.pawd.uscourts.gov/sites/pawd/files/lrmanual20181101.pdf · https://www.pawd.uscourts.gov/court-info/local-rules-and-orders/local-rules

<details><summary>Passage in the document</summary>

> …Rules of this Court. d. Requests for Admission. Requests for admission shall be governed by Fed. R. Civ. P. 36. No numerical limit on requests for admission is imposed by this Order. The parties are reminded, however, that requests for admission must be relevant to the claims or defenses in this action and must not be unduly burdensome. e. Discovery Disputes. Before filing any discovery motion, the parties must confer in good faith in an effort to resolve the dispute without court intervention, as required by Fed. R. Civ. P. 37(a)(1) and Local Rule 37.1 of the Western District of Pennsylvania. If the parties are unable to resolve a discovery dispute after conferring, either party may raise the dispute by filing a letter brief not to exceed five (5) pages, addressed to the undersigned, identifying the nature of the dispute, the efforts made to resolve it, and the relief sought. The opposing party shall have seven (7) days to file a responsive letter brief of no more than five (5) pages. The Court will determine whether further briefing or a telephonic conference is necessary. f. Electronically Stored Information. The parties shall confer regarding the preservation and production of electronically stored information ("ESI") and shall use best efforts to agree on…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: 37.1)
- **AI's reading of the rubric:** No criterion reaches the CMO's characterization of W.D. Pa. LCvR 37.1.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 10. review-counterpartys-proposed-jury-instructions — citation 76 (first ten)

- **Document:** [defense-proposed-jury-instructions.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/documents/defense-proposed-jury-instructions.docx), Instruction No. 5
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json)
- **Authority as written:** Eleventh Circuit Pattern Jury Instruction 3.1
- **Cited for:** Burden of proof - preponderance of the evidence
- **Context:** Authority: Eleventh Circuit Pattern Jury Instruction 3.1.
- **AI finding:** WRONG_CITATION_REAL_CASE
- **AI explanation:** Confirmed. In the April 2024 edition, Instruction 3.1 is "Introduction": the caption page plus "It's my duty to instruct you on the rules of law that you must use in deciding this case." It says nothing about the burden of proof. The preponderance instruction is 3.7.1: "it is the responsibility of the [Plaintiff] ... to prove every essential part of [his/her/its] claim[s] by a 'preponderance of the evidence'... simply means an amount of evidence that is enough to persuade you that [the Plaintiff's] claim is more likely true than not true." That supports the core of Proposed Instruction No. 5. The defense's "evenly balanced" paragraph is an addition, not text from 3.7.1. In the 2005 edition the burden instruction is Basic Instruction 6.1, so no edition matches 3.1. Correct cite: 11th Cir. Civ. PJI 3.7.1.
- **What the source says (AI excerpt):** “3.7.1 ... A "preponderance of the evidence" simply means an amount of evidence that is enough to persuade you that [the Plaintiff's] [the party's] claim is more likely true than not true.”
- **AI's correct citation:** Eleventh Circuit Civil Pattern Jury Instruction 3.7.1 (Responsibility for Proof - Plaintiff's Claim[s], Cross Claims, Counterclaims - Preponderance of the Evidence) (2013 ed., rev. Apr. 2024); see also Instruction 1.1 (General Preliminary Instruction, "Burden of proof")
- **Sources the AI read:** https://www.ca11.uscourts.gov/sites/default/files/courtdocs/clk/FormCivilPatternJuryInstructionsRevisedAPR2024.pdf · https://www.rid.uscourts.gov/sites/rid/files/documents/juryinstructions/otherPJI/11th%20Circuit%20Pattern%20Civil%20Jury%20Instructions.pdf

<details><summary>Passage in the document</summary>

> …sh a fact by a preponderance of the evidence means to prove that the fact is more likely true than not true. If the evidence on any issue is evenly balanced, so that you are unable to determine that the evidence supporting an issue outweighs the evidence opposing it, then your finding on that issue must be against the party who had the burden of proving it. In this case, if the plaintiff fails to meet its burden of proof on any element of a claim, you must find for the defendants on that claim. Authority: Eleventh Circuit Pattern Jury Instruction 3.1. Proposed Instruction No. 6 — Parties Are Equal Before the Law Corporations and individuals are entitled to equal treatment before the law. You must not give greater or lesser weight to the claims or defenses of any party because of whether the party is a corporation or an individual. Oakvale Technologies, Inc. and Axial Systems Corp. are each entitled to the same fair and unprejudiced treatment as an individual would receive. Similarly, Dr. Nolan Voss, as an individual, is entitled to the same fair and unprejudiced treatment as any corporate party. You should decide this case based on the evidence and the law, without regard to the nature of any party. Authority: Eleventh Circuit Pattern Ju…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: 3.1)
- **AI's reading of the rubric:** No criterion flags Instruction 5's wrong pattern number. C-029 lists No. 5 as an example of an unobjectionable instruction, which shows the author did not see the defect, but C-029 passes on any two proper instructions, so flagging this cite costs nothing.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 11. draft-opposition-to-motion-to-dismiss — citation 40 (second ten (only if needed))

- **Document:** [defendants-mtd-memorandum.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/documents/defendants-mtd-memorandum.docx), IV.A, para. 1
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json)
- **Authority as written:** Robert S. Weiss & Associates, Inc. v. Wiederlight, Robert S. Weiss & Assocs., Inc. v. Wiederlight, 208 Conn. 525, 529 (1988) (pin 529)
- **Cited for:** Courts examine whether restriction is reasonable in view of needs of parties, public and circumstances
- **Quoted as:** “is reasonable in view of the needs of the parties, the needs of the public, and the circumstances of the particular case”
- **Context:** see also Robert S. Weiss & Assocs., Inc. v. Wiederlight, 208 Conn. 525, 529 (1988) (courts examine whether restriction "is reasonable in view of the needs of the parties, the needs of the public, and the circumstances of the particular case")
- **AI finding:** MISQUOTED
- **AI explanation:** The case exists (Weiss v. Wiederlight, 208 Conn. 525, 546 A.2d 216 (1988)). At 529 it discusses the criteria for judging reasonableness, and footnote 2 lists five factors: "(1) the length of time the restriction operates; (2) the geographical area covered; (3) the fairness of the protection accorded to the employer; (4) the extent of the restraint on the employee's opportunity to pursue his occupation; and (5) the extent of interference with the public's interests." That supports the general proposition. A full-text search for "needs of" returns zero matches, so the quoted sentence is not in the opinion.
- **What the source says (AI excerpt):** “"The five factors to be considered in evaluating the reasonableness of a restrictive covenant ancillary to an employment agreement are: (1) the length of time the restriction operates; (2) the geographical area covered; (3) the fairness of the protection accorded to the employer; (4) the extent of the restraint on the employee's opportunity to pursue his occupation; and (5) the extent of interference with the public's interests." (529 n.2)”
- **AI's correct citation:** Robert S. Weiss & Assocs., Inc. v. Wiederlight, 208 Conn. 525, 529 n.2, 546 A.2d 216 (1988)
- **Sources the AI read:** https://www.courtlistener.com/opinion/7893273/weiss-v-wiederlight/

<details><summary>Passage in the document</summary>

> …trated below, Pinnacle's Complaint fails to meet this standard on every count. <u>IV. ARGUMENT</u> A. Count I Should Be Dismissed Because the Restrictive Covenant Is Facially Overbroad and Unenforceable Under Connecticut Law It is well established under Connecticut law that restrictive covenants are enforceable only if they are "reasonable in time and in the area of its restriction, considering the particular facts and circumstances." Scott v. Gen. Iron & Welding Co., 171 Conn. 132, 137 (1976); see also Robert S. Weiss & Assocs., Inc. v. Wiederlight, 208 Conn. 525, 529 (1988) (courts examine whether restriction "is reasonable in view of the needs of the parties, the needs of the public, and the circumstances of the particular case"). A restrictive covenant that exceeds what is reasonably necessary to protect the employer's legitimate business interests is unenforceable. New England Overall Co. v. Woltmann, 166 Conn. 352, 358 (1974). The employer bears the burden of demonstrating the reasonableness of each restriction. Hi-Q Personnel, Inc. v. Manning, 11 Conn. Supp. 436, 440 (1943). The RCA that Pinnacle seeks to enforce against Whitaker is overbroad in three independent respects — geographic scope, duration, and activity scope — and the Court should decline to…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** C-011 (searched for: Robert, Wiederlight)
- **AI's reading of the rubric:** No instruction or criterion asks the model to identify, flag, correct, or avoid this authority or citation errors in this document (C-063/C-009 rebut the MTD on the merits, not this misquote). C-011 does reward citing Weiss, but for reformation, a different unsupported proposition recorded separately at ref 147.

<details><summary>Text of those criteria</summary>

> **C-011. ISSUE_001 — Citation to CT reformation case law** PASS if the brief cites Connecticut case law supporting reformation of restrictive covenants (e.g., Deming v. Nationwide Mutual Insurance Co., Robert S. Weiss & Associates v. Wiederlight, or other relevant Connecticut authority on the reasonable modification standard). FAIL if no Connecticut case law on reformation or blue-penciling of non-competes is cited.

</details>

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 12. identify-issues-in-counterparty-interrogatories — citation 75 (second ten (only if needed))

- **Document:** [defense-discovery-strategy-memo.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-counterparty-interrogatories/documents/defense-discovery-strategy-memo.docx), IV.C Waiver Risk
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-issues-in-counterparty-interrogatories/task.json)
- **Authority as written:** Louisiana Stadium & Exposition Dist. v. Sedgewick Valemont, Pierce, Fenner & Smith Inc. (apparently Merrill Lynch, Pierce, Fenner & Smith Inc.), 626 F.3d 156 (2d Cir. 2010)
- **Cited for:** Second Circuit waiver of right to compel arbitration through litigation conduct (note: party name in document appears garbled relative to the reported case)
- **Context:** Louisiana Stadium & Exposition Dist. v. Sedgewick Valemont, Pierce, Fenner & Smith Inc., 626 F.3d 156 (2d Cir. 2010).
- **AI finding:** WRONG_CITATION_REAL_CASE
- **AI explanation:** The finding holds. On CourtListener, 626 F.3d 156 (cluster 179607; 2d Cir., filed 2010-11-22; also 2010 WL 4704316) is 'Louisiana Stadium & Exposition District v. Merrill Lynch, Pierce, Fenner & Smith Inc.' The memo garbles the defendant's name as 'Sedgewick Valemont, Pierce, Fenner & Smith Inc.' No case under that name exists at that cite, and no alternate reporter or name variant explains it. Volume, page, court and year are correct, and the case is a Second Circuit decision on waiver of arbitration through litigation conduct, which fits the proposition. The defect is the garbled party name.
- **What the source says (AI excerpt):** “"(1) the time elapsed from when litigation was commenced until the request for arbitration; (2) the amount of litigation to date, including motion practice and discovery; and (3) proof of prejudice." ... "we hold that LSED waived its arbitration rights."”
- **AI's correct citation:** Louisiana Stadium & Exposition Dist. v. Merrill Lynch, Pierce, Fenner & Smith Inc., 626 F.3d 156 (2d Cir. 2010)
- **Sources the AI read:** https://www.courtlistener.com/opinion/179607/louisiana-stadium-exposition-district-v-merrill-lynch-pierce-fenner/

<details><summary>Passage in the document</summary>

> …engaging in litigation conduct inconsistent with an intent to arbitrate. The relevant factors in assessing waiver include: (1) the time elapsed from the commencement of litigation to the request for arbitration; (2) the amount and extent of litigation activity — including active participation in discovery — prior to seeking arbitration; and (3) prejudice to the opposing party resulting from the inconsistent conduct. See Thyssen, Inc. v. Calypso Shipping Corp., S.A., 310 F.3d 102 (2d Cir. 2002); Louisiana Stadium & Exposition Dist. v. Sedgewick Valemont, Pierce, Fenner & Smith Inc., 626 F.3d 156 (2d Cir. 2010). Substantively responding to discovery on the merits — and particularly responding to discovery directed at the arbitration defense itself — may be cited by Trident as evidence that Whitmore has waived its right to compel arbitration. This is a real and substantial risk that must inform every discovery decision we make. <u>D. Instructions to the Team</u> The following directives are mandatory and must be followed without exception: 1. Standing Reservation of Arbitration Rights. Every discovery response, objection, interrogatory answer, and document production served by Whitmore must include the following standing reservation, to be included both in the pr…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: Louisiana, Sedgewick)
- **AI's reading of the rubric:** Strategy memo garbles the party name of Louisiana Stadium v. Merrill Lynch (cite and proposition correct); C-033/C-034 address arbitration-waiver risk without citing or testing this case.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 13. assess-settlement-value-range — citation 84 (second ten (only if needed))

- **Document:** [defense-mediation-brief.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-settlement-value-range/documents/defense-mediation-brief.docx), IV.A Economic Damages, Discount Rate / III.A para 3 (Ohio law on compliance with standards)
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-settlement-value-range/task.json)
- **Authority as written:** Ohio law on compliance with industry safety standards as evidence of non-defect
- **Cited for:** Under Ohio law, compliance with applicable industry safety standards at time of manufacture is strong evidence a product was not defectively designed
- **Quoted as:** “generally recognized and prevailing standard”
- **Context:** Under Ohio law, compliance with applicable industry safety standards at the time of manufacture, while not dispositive of the design defect inquiry, is strong evidence that a product was not defectively designed.
- **AI finding:** MISCHARACTERIZED
- **AI explanation:** I read R.C. 2307.75 on codes.ohio.gov. Division (F) is the no-feasible-alternative-design provision: 'A product is not defective in design or formulation if, at the time the product left the control of its manufacturer, a practical and technically feasible alternative design or formulation was not available...'. The phrase 'generally recognized and prevailing standard' does not appear anywhere in the section. Standards appear only in (B)(4), as one risk factor: 'The extent to which that design or formulation conformed to any applicable public or private product standard that was in effect when the product left the control of its manufacturer.' So the statute treats conformity as a relevant factor, not as a safe harbor or 'strong evidence'. The brief invents a quoted safe harbor and attributes it to (F). The general idea that compliance is relevant but not dispositive gets some support from (B)(4), but the cited provision and the quoted language do not.
- **What the source says (AI excerpt):** “(B)(4) The extent to which that design or formulation conformed to any applicable public or private product standard that was in effect when the product left the control of its manufacturer ... (F) A product is not defective in design or formulation if ... a practical and technically feasible alternative design or formulation was not available”
- **AI's correct citation:** O.R.C. § 2307.75(B)(4)
- **Sources the AI read:** https://codes.ohio.gov/ohio-revised-code/section-2307.75

<details><summary>Passage in the document</summary>

> … simultaneous activation by both hands, ensuring both hands are clear of the point of operation before the ram descends; (2) a fixed barrier guard with a maximum gap of 1 inch between the guard and the press bed, meeting ANSI B11.2 specifications for point-of-operation guarding; (3) an accessible emergency stop mechanism, prominently positioned on the operator's control panel; and (4) a single safety interlock on the hydraulic control circuit designed to prevent unintended cycling of the press. Under Ohio law, compliance with applicable industry safety standards at the time of manufacture, while not dispositive of the design defect inquiry, is strong evidence that a product was not defectively designed. Ohio Revised Code § 2307.75(F) provides that a product is not defective in design if it conformed to a "generally recognized and prevailing standard" at the time it left the control of the manufacturer. The GP-7500's conformity with ANSI B11.2 requirements — the prevailing national consensus standard for hydraulic press safety — creates a substantial evidentiary presumption against plaintiff's design defect claim. While this presumption is rebuttable, plaintiff bears a heavy burden to demonstrate that the GP-7500's design was unreasonably dangerous notwithstand…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none
- **AI's reading of the rubric:** Same R.C. 2307.75 standards-compliance defect as ref 41; no criterion reaches it.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 14. draft-motion-for-summary-judgment — citation 48 (second ten (only if needed))

- **Document:** [plaintiff-interrogatory-responses.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/documents/plaintiff-interrogatory-responses.docx), Interrogatory No. 7 (response)
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-summary-judgment/task.json)
- **Authority as written:** Rule 33(a)(2) (pin (a)(2))
- **Cited for:** Objection that contention interrogatory seeks legal theories and mental impressions
- **Context:** further objecting to the extent that this interrogatory is a contention interrogatory that seeks disclosure of Plaintiff's legal theories and mental impressions in a manner inconsistent with Rule 33(a)(2)
- **AI finding:** MISCHARACTERIZED
- **AI explanation:** The finding mostly holds, though it slightly overstates the problem. Rule 33(a)(2) (LII) says: "An interrogatory is not objectionable merely because it asks for an opinion or contention that relates to fact or the application of law to fact." The 1970 advisory committee note bars only questions of "pure law", meaning "legal issues unrelated to the facts of the case." The objection is hedged "to the extent" and could be read as invoking that pure-law limit, which partly blunts the finding. Even so, Interrogatory No. 7 asks only to "State with specificity all facts supporting your claim", which is a fact-based contention the rule expressly permits. Rule 33(a)(2) also says nothing about protecting "mental impressions"; that protection is work product under Rule 26(b)(3). Citing the rule that authorizes contention interrogatories as the basis for objecting to one, and as the source of mental-impressions protection, misstates what it does.
- **What the source says (AI excerpt):** “"An interrogatory is not objectionable merely because it asks for an opinion or contention that relates to fact or the application of law to fact, but the court may order that the interrogatory need not be answered until designated discovery is complete, or until a pretrial conference or some other time."”
- **AI's correct citation:** Fed. R. Civ. P. 33(a)(2); work-product protection for mental impressions is Fed. R. Civ. P. 26(b)(3)
- **Sources the AI read:** https://www.law.cornell.edu/rules/frcp/rule_33

<details><summary>Passage in the document</summary>

> …ments, comments, remarks, or communications by any Whitaker employee that you contend were racially motivated or reflected racial animus; (b) any actions, decisions, or patterns of conduct by any Whitaker employee that you contend were racially motivated; (c) any statistical or documentary evidence you contend supports an inference of racial discrimination; and (d) the identity of any witness to any of the foregoing. RESPONSE: Subject to and without waiving the foregoing general objections, and further objecting to the extent that this interrogatory is a contention interrogatory that seeks disclosure of Plaintiff's legal theories and mental impressions in a manner inconsistent with Rule 33(a)(2), Plaintiff responds as follows: Plaintiff Denise Huang was, upon information and belief, the only Asian-American individual holding a senior sales leadership position at the level of Regional Sales Director or above at Whitaker Industrial Supply Co. at the time of her termination. Plaintiff is not aware of any other Asian-American employee who has held the title of Regional Sales Director, Vice President of Sales, or Senior Vice President of Sales at Whitaker during the period of her employment from February 2018 through March 2023. Plaintiff contends that Thomas Breck…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: 33(a))
- **AI's reading of the rubric:** No criterion reaches the interrogatory response's Rule 33(a)(2) objection.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 15. assess-settlement-value-range — citation 122 (second ten (only if needed))

- **Document:** [comparable-outcomes-summary.xlsx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-settlement-value-range/documents/comparable-outcomes-summary.xlsx), Comparable Outcomes, row 6 (B6)
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-settlement-value-range/task.json)
- **Authority as written:** Williams v. PressForce Corp. (Hamilton County, OH, 2019)
- **Cited for:** Four-finger amputation; plaintiff bypassed guard; $3.9M settlement
- **Context:** Settlement of $3.9M despite disputed liability and plaintiff fault suggests Holt matter should command a higher figure.
- **AI finding:** NOT_FOUND_LIKELY_FABRICATED
- **AI explanation:** The finding holds. CourtListener had no opinion or docket for 'PressForce'. A web search for the exact phrase "Williams v. PressForce" with Ohio settlement terms returned only unrelated Ohio cases named Williams. The case is described as an unreported Hamilton County settlement, so it can never be completely ruled out. It appears only in the scenario documents, alongside the other invented comparables.
- **What the source says (AI excerpt):** “B6: Williams v. PressForce Corp. / C6: Hamilton County, OH (State Court) / D6: 2019 ... N6: $3,900,000”
- **Sources the AI read:** https://www.courtlistener.com/?q=caseName%3A%28Williams+AND+PressForce%29

<details><summary>Passage in the document</summary>

> … Significant comparative fault to plaintiff for bypassing guard K6: Not specified L6: No — plaintiff bypassed existing guard (no employer modification) M6: Settlement N6: $3,900,000 O6: N/A (settlement) P6: $3,900,000 Q6: N/A R6: Not separately stated S6: Less severe injury than Holt (finger amputation vs. below-elbow amputation). Strong comparative fault to plaintiff for bypassing guard — distinguishable because Holt did not bypass any guard; Apex modified the guard without Holt's involvement. Settlement of $3.9M despite disputed liability and plaintiff fault suggests Holt matter should command a higher figure. T6: 3 A7: 6 B7: Ostrowski v. Columbian Machine Works C7: Cuyahoga County, OH (State Court) D7: 2020 E7: Defense F7: Hydraulic press G7: Partial hand amputation H7: N/A I7: Strong comparative fault argument — plaintiff had personally removed safety guard J7: Significant comparative fault to plaintiff for removing guard K7: Not specified L7: No — plaintiff (not employer) removed guard M7: Settlement N7: $2,100,000 O7: N/A (settlement) P7: $2,100,000 Q7: N/A R7: Not separately stated S7: Defense-favorable comparable. Less severe injury (partial hand vs. below-elbow amputation). Key distinguishing factor: plaintiff personally removed the guard, whereas in …

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: Williams, PressForce)
- **AI's reading of the rubric:** Fictional scenario comparable; no criterion asks the model to verify it, and no criterion names Williams v. PressForce.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 16. draft-motion-to-dismiss-brief — citation 287 (second ten (only if needed))

- **Document:** [arcadias-response-to-meridians-dtpa-letter.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/documents/arcadias-response-to-meridians-dtpa-letter.docx), Part II, paragraph beginning 'We are prepared to produce'
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json)
- **Authority as written:** Cameron v. Terrell & Garrett, Inc., 618 S.W.2d 535, 541 (Tex. 1981) (pin 541)
- **Cited for:** DTPA exemptions are affirmative defenses to be proved by the party claiming them
- **Context:** the burden of establishing the applicability of a DTPA exemption rests on the party asserting it — in this case, Meridian. See Cameron v. Terrell & Garrett, Inc., 618 S.W.2d 535, 541 (Tex. 1981) (exemptions from the DTPA are affirmative defenses to be proved by the party claiming them).
- **AI finding:** MISCHARACTERIZED
- **AI explanation:** I could not refute this finding. On CourtListener (opinion 1527473), the cite 618 S.W.2d 535 resolves to Cameron v. Terrell & Garrett, Inc. (Tex. Mar. 4, 1981), so the case and reporter cite are real. But the opinion contains 0 hits for "burden" and 0 hits for "affirmative." Its only discussion of § 17.49 is a statutory-breadth point at 540: "The breadth of the Act is evidenced by section 17.49 which sets out the exemptions to the DTPA. That section does not provide an exemption for deceptive trade practices by persons who do not furnish the goods or services ... it only exempts from the Act certain media owners and employees." The pin page 541 is about privity: "We find no indication ... that the legislature intended to restrict its application only to deceptive trade practices committed by persons who furnish the goods or services [*541] on which the complaint is based. Nor do we find any indication that the legislature intended to restrict its application by any other similar privity requirement." Cameron does not hold that DTPA exemptions are affirmative defenses that the party claiming them must prove. The parenthetical states a holding the case does not contain.
- **What the source says (AI excerpt):** “Cameron at 540-41: "The breadth of the Act is evidenced by section 17.49 which sets out the exemptions to the DTPA. That section does not provide an exemption for deceptive trade practices by persons who do not furnish the goods or services on which the complaint is based." ... "We, therefore, hold that a person need not seek or acquire goods or services furnished by the defendant to be a consumer as defined in the DTPA." Eckman: "we hold that the defendant has the burden to plead and prove the applicability of the $25,000,000 exception to business consumer status as an affirmative defense."”
- **AI's correct citation:** Eckman v. Centennial Savings Bank, 784 S.W.2d 672, 674-76 (Tex. 1990) (defendant has the burden to plead and prove the $25,000,000 business-consumer exception as an affirmative defense)
- **Sources the AI read:** https://www.courtlistener.com/opinion/1527473/cameron-v-terrell-garrett-inc/

<details><summary>Passage in the document</summary>

> …et threshold. As reflected in Arcadia's audited financial statements for the fiscal year ending December 31, 2022, Arcadia's total assets as of its most recent fiscal year-end were $23.8 million. This figure is below the $25 million statutory threshold. Accordingly, Section 17.49(f) does not exempt Meridian from DTPA liability in this matter. We are prepared to produce Arcadia's audited financial statements in connection with any challenge Meridian may raise to this representation. We note that the burden of establishing the applicability of a DTPA exemption rests on the party asserting it — in this case, Meridian. See Cameron v. Terrell & Garrett, Inc., 618 S.W.2d 535, 541 (Tex. 1981) (exemptions from the DTPA are affirmative defenses to be proved by the party claiming them). Meridian cannot simply presume that Arcadia's total assets exceed $25 million based on Arcadia's annual revenue or the size of the transaction at issue. We further note that total assets under Section 17.49(f) is a defined accounting concept, referring to the aggregate book value of all assets reported on the entity's balance sheet. Arcadia's annual revenue of approximately $62 million does not translate to total assets of $25 million or more; Arcadia operates in a services-oriented sect…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: Cameron, Terrell)
- **AI's reading of the rubric:** Authority in Arcadia's DTPA letter; no criterion names it or asks the model to rebut the letter's authorities.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 17. draft-opposition-to-motion-to-dismiss — citation 23 (second ten (only if needed))

- **Document:** [verified-complaint.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/documents/verified-complaint.docx), Prayer for Relief (e)
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json)
- **Authority as written:** DTSA and CUTSA attorneys' fees, 18 U.S.C. § 1836(b)(3)(D); Conn. Gen. Stat. § 35-52(c)
- **Cited for:** Attorneys' fees and costs
- **Context:** pursuant to the Defend Trade Secrets Act, 18 U.S.C. § 1836(b)(3)(D), and the Connecticut Uniform Trade Secrets Act, Conn. Gen. Stat. § 35-52(c)
- **AI finding:** WRONG_CITATION_REAL_CASE
- **AI explanation:** As with ref 22, the DTSA half was not re-read here; the first reviewer verified it on LII. The CUTSA half is mis-cited. § 35-52(c) concerns only court-compelled "affirmative acts to protect a trade secret." The fee authority is § 35-53(b) ("may award reasonable attorney's fees to the prevailing party" on wilful and malicious misappropriation), with § 35-54 covering bad-faith claims. As the first reviewer noted, neither CUTSA provision mentions costs.
- **What the source says (AI excerpt):** “§ 1836(b)(3)(D): "or the trade secret was willfully and maliciously misappropriated, award reasonable attorney's fees to the prevailing party." Conn. Gen. Stat. § 35-52(c): "In appropriate circumstances, affirmative acts to protect a trade secret may be compelled by court order." § 35-53(b): "if the court finds wilful and malicious misappropriation, the court may award punitive damages in an amount not exceeding twice any award made under subsection (a) and may award reasonable attorney's fees to the prevailing party."”
- **AI's correct citation:** 18 U.S.C. § 1836(b)(3)(D); Conn. Gen. Stat. § 35-53(b) (attorney's fees on a finding of wilful and malicious misappropriation); see also Conn. Gen. Stat. § 35-54 (attorney's fees for bad-faith claims or motions).
- **Sources the AI read:** https://www.cga.ct.gov/current/pub/chap_625.htm · https://www.law.cornell.edu/uscode/text/18/1836

<details><summary>Passage in the document</summary>

> …njust enrichment of Defendants resulting from their misappropriation of Pinnacle's trade secrets and interference with Pinnacle's business relationships; > > (d) Exemplary damages of up to two (2) times actual damages under the Defend Trade Secrets Act, 18 U.S.C. § 1836(b)(3)(C), and the Connecticut Uniform Trade Secrets Act, Conn. Gen. Stat. § 35-52(b), based on Defendants' willful and malicious misappropriation; > > (e) Reasonable attorneys' fees and costs incurred by Pinnacle in this action, pursuant to the Defend Trade Secrets Act, 18 U.S.C. § 1836(b)(3)(D), and the Connecticut Uniform Trade Secrets Act, Conn. Gen. Stat. § 35-52(c); > > (f) Punitive damages against Defendant Lodestar for tortious interference with Pinnacle's business relationships, in an amount sufficient to punish Lodestar's willful and malicious conduct and to deter similar conduct in the future; > > (g) Disgorgement of any profits, compensation, or other economic benefit derived by either Defendant from the misappropriation of Pinnacle's trade secrets and the interference with Pinnacle's business relationships; > > (h) Pre-judgment and post-judgment interest at the maximum rate permitted by law; > > (i) Such other and further relief as this Court deems just, equitable, and proper. <u>JU…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** C-024, C-035 (searched for: 1836(b), 52(c))
- **AI's reading of the rubric:** No instruction or criterion asks the model to identify, flag, correct, or avoid this authority or citation errors in this document; C-047 cites CUTSA only generally as Conn. Gen. Stat. § 35-50 et seq., not § 35-52 for remedies.

<details><summary>Text of those criteria</summary>

> **C-024. ISSUE_006 — Broad construction of DTSA commerce element** PASS if the brief notes or argues that the interstate commerce element under 18 U.S.C. § 1836(b)(1) is broadly construed by courts and is satisfied where the trade secret is related to a product or service used in or intended for use in interstate commerce. FAIL if the brief does not discuss the breadth of the DTSA commerce element or cite 18 U.S.C. § 1836.
>
> **C-035. ISSUE_011 — DTSA provides for threatened misappropriation** PASS if the brief argues that under the DTSA, threatened misappropriation is independently actionable, citing or referencing 18 U.S.C. § 1836(b)(3)(A) or the statutory provision allowing relief for threatened misappropriation. FAIL if the brief does not invoke the DTSA's provision for threatened misappropriation in addressing the ripeness argument.

</details>

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 18. review-counterpartys-proposed-jury-instructions — citation 88 (second ten (only if needed))

- **Document:** [defense-proposed-jury-instructions.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/documents/defense-proposed-jury-instructions.docx), Instruction No. 15
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json)
- **Authority as written:** Penalty Kick Mgmt. Ltd. v. Coca Cola Co., 318 Ga. App. 586 (2012)
- **Cited for:** Definition of 'readily ascertainable'
- **Context:** Authority: O.C.G.A. § 10-1-761(4); Penalty Kick Mgmt. Ltd. v. Coca Cola Co., 318 Ga. App. 586 (2012).
- **AI finding:** CITATION_POINTS_TO_DIFFERENT_CASE
- **AI explanation:** The finding holds. CourtListener citation lookup resolves 318 Ga. App. 586 to Dodson v. Walraven (Ga. Ct. App. Nov. 16, 2012). That opinion opens: "Following a bench trial, Douglas Dodson appeals from an order establishing custody of his minor child and his child support obligations," and a search of its text finds no match for "trade secret." A case-name search turns up only two Penalty Kick decisions: N.D. Ga., 164 F. Supp. 2d 1376 (2001), and 11th Cir., 318 F.3d 1284 (2003). There is no Georgia Court of Appeals Penalty Kick opinion. One mitigating note: the record's own SJ Order cites Penalty Kick with the same wrong reporter ("318 Ga. App. 586, 591 (2012)"), so the error may have been copied from it. The plaintiff's brief cites the correct 318 F.3d 1284. On substance, the 11th Circuit opinion uses "readily ascertainable" only once, at 1291, where it quotes § 10-1-761(4). It gives no definition of the term like Instruction 15's.
- **What the source says (AI excerpt):** “318 Ga. App. 586: "DOYLE, Presiding Judge. Following a bench trial, Douglas Dodson appeals from an order establishing custody of his minor child and his child support obligations to Sarah Walraven". Penalty Kick, 318 F.3d at 1291: "(A) Derives economic value, actual or potential, from not being generally known to, and not being readily ascertainable by proper means by, other persons"”
- **AI's correct citation:** Penalty Kick Mgmt. Ltd. v. Coca Cola Co., 318 F.3d 1284 (11th Cir. 2003)
- **Sources the AI read:** https://www.courtlistener.com/opinion/7928139/dodson-v-walraven/ · https://www.courtlistener.com/opinion/780794/penalty-kick-management-ltd-v-coca-cola-company/

<details><summary>Passage in the document</summary>

> … consider that fact in determining whether the information qualifies as a trade secret under the Georgia Trade Secrets Act. The fact that information could have been discovered through proper means does not automatically disqualify it as a trade secret; rather, it is one factor for you to consider in making your determination. The focus of your inquiry should be on whether the information was, in fact, readily obtainable by persons outside Oakvale Technologies, Inc. through legitimate channels. Authority: O.C.G.A. § 10-1-761(4); Penalty Kick Mgmt. Ltd. v. Coca Cola Co., 318 Ga. App. 586 (2012). Proposed Instruction No. 16 — Definition of "Misappropriation" Under the Georgia Trade Secrets Act, "misappropriation" means the acquisition of a trade secret of another by a person who knows or has reason to know that the trade secret was acquired by improper means. "Improper means" includes theft, bribery, misrepresentation, breach or inducement of a breach of a duty to maintain secrecy, or espionage through electronic or other means. Proper means of acquiring information, such as independent discovery, reverse engineering, or observation of publicly available products, do not constitute misappropriation. To prevail on its misappropriation claim, the plaintiff must pr…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: Penalty, Coca)
- **AI's reading of the rubric:** No criterion flags Instruction 15's Penalty Kick cite (Ga. App. reporter cite that resolves to a different case). C-029 names No. 15 as an example of a proper instruction, showing the author missed the defect, but credit does not require naming it.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 19. research-corporate-veil-piercing-standards-across-target-jurisdictions — citation 11 (second ten (only if needed))

- **Document:** [iepa-enforcement-complaint.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/documents/iepa-enforcement-complaint.docx), Para. 31
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/research-corporate-veil-piercing-standards-across-target-jurisdictions/task.json)
- **Authority as written:** 40 C.F.R. § 262.17 and 35 Ill. Admin. Code § 722.134, 40 C.F.R. § 262.17; 35 Ill. Admin. Code § 722.134
- **Cited for:** Ninety-day generator accumulation limits exceeded, triggering permit requirement
- **Context:** exceeded the ninety-day generator accumulation limits established under 40 C.F.R. § 262.17 and 35 Ill. Admin. Code § 722.134
- **AI finding:** WRONG_CITATION_REAL_CASE
- **AI explanation:** The finding holds. The federal cite (40 C.F.R. 262.17) is accurate. The Illinois cite is stale. The official JCAR page reads 'Section 722.134 Accumulation Time (Repealed) (Source: Repealed at 42 Ill. Reg. 22047, effective November 19, 2018)', and LII shows the same. The complaint alleges violations in 2023-2024. The operative Illinois rule is 35 Ill. Adm. Code 722.117(a): 'The LQG may accumulate hazardous waste on site for no more than 90 days', and 722.117(b) says an LQG accumulating more than 90 days 'is subject to the requirements of 35 Ill. Adm. Code 702, 703, and 724 through 728'. The substantive rule exists and supports the proposition, but the section number is wrong (repealed).
- **What the source says (AI excerpt):** “Ill. Admin. Code tit. 35, § 722.134 - Accumulation Time (Repealed) ... Repealed at 42 Ill. Reg. 22047, effective 11/19/2018”
- **AI's correct citation:** 40 C.F.R. § 262.17(a)-(b); 35 Ill. Adm. Code 722.117(a)-(b) (35 Ill. Adm. Code 722.134 was repealed effective Nov. 19, 2018)
- **Sources the AI read:** https://www.ilga.gov/commission/jcar/admincode/035/035007220C01340R.html · https://www.law.cornell.edu/regulations/illinois/Ill-Admin-Code-tit-35-SS-722.134 · https://www.law.cornell.edu/regulations/illinois/Ill-Admin-Code-tit-35-SS-722.117

<details><summary>Passage in the document</summary>

> …ighty-four thousand (84,000) gallons of spent hydraulic fluid at the Canton Facility (4,200 gallons/month × 20 months = 84,000 gallons). 30. The spent hydraulic fluid was stored in above-ground tanks and drum storage areas at the Canton Facility. These storage units lacked secondary containment, leak detection systems, and other safeguards required under 40 C.F.R. Part 265, Subpart J, for hazardous waste storage facilities. 31. The Canton Facility's storage of spent hydraulic fluid consistently exceeded the ninety-day generator accumulation limits established under 40 C.F.R. § 262.17 and 35 Ill. Admin. Code § 722.134, thereby triggering the requirement to obtain a hazardous waste storage permit. At no time during the violation period did Pryor possess a RCRA interim status permit, a RCRA permit, or any other applicable hazardous waste storage authorization for the Canton Facility. 32. Periodically during the violation period, Pryor shipped quantities of spent hydraulic fluid from the Canton Facility to Greenfield Environmental Services, a licensed TSDF in Peoria, Illinois, for treatment and disposal. The hazardous waste manifests accompanying these shipments contained inaccurate waste characterization information, including the misidentification of waste codes…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: 262.17, 722.134)
- **AI's reading of the rubric:** No criterion reaches the cite to repealed 35 Ill. Admin. Code § 722.134.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

## 20. assess-settlement-value-range — citation 86 (second ten (only if needed))

- **Document:** [aldrich-economic-report.docx](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-settlement-value-range/documents/aldrich-economic-report.docx), Section IV, Past Medical Expenses, para. 5 (line 89)
- **Task file (instructions and rubric):** [task.json](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-settlement-value-range/task.json)
- **Authority as written:** Ohio Revised Code § 2315.20
- **Cited for:** Collateral source rule permits recovery of the full value of medical services regardless of the source of payment
- **Context:** Under Ohio Revised Code § 2315.20 and applicable Ohio case law, the collateral source rule permits recovery of the full value of medical services regardless of the source of payment.
- **AI finding:** MISCHARACTERIZED
- **AI explanation:** R.C. 2315.20(A) says 'the defendant may introduce evidence of any amount payable as a benefit to the plaintiff ... except if the source of collateral benefits has ... a statutory right of subrogation...'. Under (B), the plaintiff may then show what it paid to secure those benefits. Read fairly, the subrogation exception would keep the workers' compensation benefits in this case out of evidence, which gives the report's gross approach some partial support. But the statute says nothing about recovering the 'full value of medical services regardless of the source of payment'. It is a partial abrogation that lets defendants introduce collateral benefits. The 'applicable Ohio case law' also cuts against a full-billed-value rule. Robinson v. Bates, 112 Ohio St.3d 17 (2006), holds: 'Both the original medical bill rendered and the amount accepted as full payment are admissible...' and that 'the reasonable value of medical services is a matter for the jury to determine from all relevant evidence.' The proposition misstates the statute.
- **What the source says (AI excerpt):** “(A) In any tort action, the defendant may introduce evidence of any amount payable as a benefit to the plaintiff as a result of the damages that result from an injury ... except if the source of collateral benefits has a mandatory self-effectuating federal right of subrogation, a contractual right of subrogation, or a statutory right of subrogation”
- **Sources the AI read:** https://codes.ohio.gov/ohio-revised-code/section-2315.20 · https://www.courtlistener.com/opinion/6789871/robinson-v-bates/

<details><summary>Passage in the document</summary>

> …alf of Mr. Holt through its workers' compensation coverage as of January 15, 2025. The total medical charges billed exceed the workers' compensation payments because some charges were paid by Mr. Holt's personal health insurance through his spouse's employer-sponsored plan, and certain balances remain outstanding. The $363,700 figure I report represents the total incurred medical cost — that is, the amount charged for all medical services rendered — not the amount paid by any particular source. Under Ohio Revised Code § 2315.20 and applicable Ohio case law, the collateral source rule permits recovery of the full value of medical services regardless of the source of payment. Accordingly, my calculation of past medical expenses reflects the total cost of the medical care Mr. Holt received, without reduction for workers' compensation payments, health insurance payments, or any other collateral source. I further note that Buckeye Mutual Workers' Comp Fund has asserted a statutory subrogation lien of $481,800 against any tort recovery obtained by Mr. Holt in this litigation. This lien comprises $418,600 in medical benefits and $63,200 in temporary total disability benefits paid by Buckeye Mutual through January 15, 2025. Under Ohio Revised Code § 4123.93, a workers…

</details>

**How the rubric treats it**

- **Does the rubric ask the model to catch this error?** No. An AI review of the task instructions and every criterion found no criterion targeting it.
- **Does a criterion reward relying on it?** No.
- **Criteria that name this authority:** none (searched for: 2315.20)
- **AI's reading of the rubric:** Aldrich report's collateral-source characterization of R.C. 2315.20; C-011/C-012 address the workers' comp lien amount and its effect on net recovery, not the collateral-source statute.

- **Verdict:** 
- **Error type, if confirmed:** 
- **Rubric relevance (optional):** 
- **Note:** 

