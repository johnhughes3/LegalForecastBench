# Citation checks: lrb-certiorari-quasi-judicial-land-use

AI-generated citation checks, not human legal verification or score corrections. The counting unit is a citation in a unique matter document, not each repeated assignment packet. Worker file lists and limits are reproduced below; absence of a stated limit does not independently establish exhaustive coverage. Completion requires an explicit census-complete judgment; verification limits remain visible. Every first-check problem requires an independent second check, including overturned findings. Missing files and pending checks never establish a zero-problem result.

Model: Claude Opus 5.5; reasoning effort: high.

Worker coverage: {'files_read': ['https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/instruction.md', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/tests/fixtures/rubric.json', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-2/instruction.md', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-2/tests/fixtures/rubric.json', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-petition.docx', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-lcu-project.pdf'], 'limits': ["Both assignments carry the same four attachments (byte-identical conversions), so each attachment is counted once. Assignment 2's input repeats the assignment-1 prompt; only each assignment's own current prompt is counted.", 'The Order (orderpdf.docx) is six scanned page images with no text layer; the packet conversion contains only image tags. All six pages were read visually from the images embedded in the pinned original DOCX (no OCR). The service list on page 6 (email addresses) is not reproduced.', 'The LCU Project PDF has no text layer beyond browser headers; its five pages were rendered and read visually. It contains no legal citations.', "The Petition's 28 embedded images (maps, charts, photos, a deed cover page, FAA figure, tax-roll screenshots) were reviewed at contact-sheet scale; the fine-print notes on images 14, 16, 25 and 26 were not legible and were not read. Images 11-12 reproduce FAA AC Figure 1 and were checked.", "The Resolution is OCR-derived text with garbles (e.g., '34-41 1' for 34-411, '10-41 8' for 10-418, '50-17.05' for 5J-17.05); several pin cites sit in inline images, which were read (image 7 '(h).', image 9 '34-377('). Recorded-instrument references (ORB/ORI numbers) in the legal description and plan are not treated as legal authority.", "Lee Plan goal/objective/policy/map citations in the Resolution's findings were not checked against the Lee Plan; they are UNABLE_TO_VERIFY.", "Record citations to non-law sources (Petition.docx pages, LCU Project.pdf pages, the Lee County DCD application web page, the Florida courts jurisdiction map, transcripts, staff reports, the 2017 Biological Opinion, the SFWMD water supply plan, the Kingston settlement instrument) are not counted. Rubric citations to the Order ('Order.docx at N') are counted as citations to the circuit court's order and checked against its page images.", "Lee County LDC chapters 2, 10 and 34 and Code of Ordinances chapter 11 were read from Municode's current versions (as of 2026); each section's amendment history was checked. Where a cited section was amended after the document it appears in (LDC ss. 10-261, 10-291, 10-321, 10-329, 10-416, 10-418: Ord. 24-14, Oct. 2024, or Ord. 25-09, Apr. 2025), the pre-amendment text was not retrieved; those entries are VERIFIED only because the cited requirement appears in the current text, and say so. LDC s. 34-145 visibly changed (Oct. 2024, Apr. 2025) and is UNABLE_TO_VERIFY. Admin. Code AC-2-6 was read in its 8/2/22 version; the version in force in 2019-20 was not read.", 'Florida Statutes were read in the 2024 edition (with 2023 for s. 333.03). Appellate rules were read from rules.floridaappellate.com; the Florida Bar rules PDFs and Fla. R. Gen. Prac. & Jud. Admin. 2.520 could not be downloaded.', 'The Smith Florida Law Review article PDF was blocked (HTTP 403); only its repository landing page was read. Babcock (1966) and Mandelker & Tarlock (1992) were not read; they appear only inside a Snyder quotation that was verified.', "AC 150/5200-33B and AC 150/5300-13A (cancelled) and AC 150/5300-13B and 150/5200-30D were identified from FAA's current and cancelled AC lists; their texts were not read. AC 150/5190-4B, 150/5200-33C and 150/5190-7 were read in full text.", "Generic references with no identifiable provision (e.g., 'Florida's Sunshine Law', 'the Land Development Code', 'Federal regulations') are not counted separately; authorities embedded in quoted text (LDC s. 34-1102's list, s. 333.02's cross-reference, the Biological Opinion's 50 CFR 402.16 and CWA s. 404, the AC's ESA s. 7) are counted once per quoted block.", 'Integration coverage review preserves the first judgments but marks nine FAA index-only checks and eight current-only code checks UNABLE_TO_VERIFY. The cited circular texts or applicable historical code versions were not read. These are coverage limits, not established citation errors.', 'The Sol second pass rechecked all 27 initial problem rows and added a Part 150 citation. It raised five new problems (refs29,78,87,89,136), promoted here to new first-stage findings with initial judgments preserved. Independent review of those five is pending. The two nonproblem supplemental checks remain separately saved pending further primary-source reading.'], 'counting_unit': 'citation occurrence in each unique matter document, separate prompt and rubric occurrences', 'census_complete': False}

## 0: Spahn v. Lee County (Fla. 20th Cir. Ct.)

Document: assignment-1 instruction.md (prompt); location: RE line.

Authority type: case; as written: PETER SPAHN, ET. AL., V. LEE COUNTY; Case No. 24-CA-1479; pincite: .

Cited for: Identifies the circuit-court certiorari case whose Order the memo addresses

Quotes: []

Context: RE: PETER SPAHN, ET. AL., V. LEE COUNTY; Case No. 24-CA-1479

Fictional by design: False; 

### First check: VERIFIED

The Order (read from its six page images in the pinned DOCX) is captioned in the Twentieth Judicial Circuit, Lee County, Case No. 24-CA-1479, Petitioners Peter Spahhn [sic], Marsha Ellis, Serge Thomas v. Lee County. The caption misspells the first petitioner; the Order's body (p.5) spells it Spahn, matching the prompt.

Excerpt read: Order p.1: "PETER SPAHHN, MARSHA ELLIS, SERGE THOMAS Petitioners. v. Case No: 24-CA-1479 LEE COUNTY"; p.5: "Petitioner Peter Spahn's residence".

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx

### Second check: not required


## 1: Lee County, Fla., Resolution No. Z-23-035

Document: assignment-1 instruction.md (prompt); location: record list.

Authority type: other; as written: Resolution Z-23-035 (Resolution.docx); pincite: .

Cited for: The rezoning resolution supplied as part of the record

Quotes: []

Context: Resolution Z-23-035 (Resolution.docx)

Fictional by design: False; 

### First check: VERIFIED

The supplied resolution is Lee County Resolution No. Z-23-035, adopted January 17, 2024, rezoning the 112.21-acre parcel (DCI2023-00011) from AG-2 to CFPD.

Excerpt read: "RESOLUTION NUMBER Z-23-035 ... DULY PASSED AND ADOPTED this 17th day of January 2024."

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx

### Second check: not required


## 2: Spahn v. Lee County (Fla. 20th Cir. Ct.)

Document: assignment-2 instruction.md (prompt); location: RE line.

Authority type: case; as written: PETER SPAHN, ET. AL., V. LEE COUNTY; Case No. 24-CA-1479; pincite: .

Cited for: Identifies the case whose Order is to be appealed

Quotes: []

Context: RE: PETER SPAHN, ET. AL., V. LEE COUNTY; Case No. 24-CA-1479

Fictional by design: False; 

### First check: VERIFIED

The Order (read from its six page images in the pinned DOCX) is captioned in the Twentieth Judicial Circuit, Lee County, Case No. 24-CA-1479, Petitioners Peter Spahhn [sic], Marsha Ellis, Serge Thomas v. Lee County. The caption misspells the first petitioner; the Order's body (p.5) spells it Spahn, matching the prompt.

Excerpt read: Order p.1: "PETER SPAHHN, MARSHA ELLIS, SERGE THOMAS Petitioners. v. Case No: 24-CA-1479 LEE COUNTY"; p.5: "Petitioner Peter Spahn's residence".

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx

### Second check: not required


## 3: Lee County, Fla., Resolution No. Z-23-035 (2024)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #0 states_in_the_first_assignment_that_the_order_granting_petition (criterion).

Authority type: other; as written: Lee County, Fla., Res. No. Z-23-035 (2024); pincite: .

Cited for: The resolution the Order quashes

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The supplied resolution is Lee County Resolution No. Z-23-035, adopted January 17, 2024, rezoning the 112.21-acre parcel (DCI2023-00011) from AG-2 to CFPD.

Excerpt read: "RESOLUTION NUMBER Z-23-035 ... DULY PASSED AND ADOPTED this 17th day of January 2024."

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx

### Second check: not required


## 4: Order Granting Petition for Writ of Certiorari, Spahn v. Lee County, No. 24-CA-1479

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #0 (source).

Authority type: case; as written: Order.docx at 1; pincite: 1.

Cited for: Order grants the petition and quashes the rezoning

Quotes: ['the petition for writ of certiorari is hereby GRANTED and the rezoning is QUASHED for the reasons discussed below.']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Order p.1 reads "the Petition for Writ of Certiorari is hereby GRANTED and the rezoning is hereby QUASHED for the reasons discussed below." The rubric drops the second "hereby". Note the decretal paragraph on p.6 says the decision below is "REVERSED", not quashed.

Excerpt read: p.1: "...is hereby GRANTED and the rezoning is hereby QUASHED for the reasons discussed below." p.6: "...is GRANTED and the decision below is REVERSED."

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx

### Second check: not required


## 5: Order Granting Petition for Writ of Certiorari

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #1 states_in_the_first_assignment_that_the_circuit_court_found_that (source).

Authority type: case; as written: Order.docx at 2; pincite: 2.

Cited for: Court found petitioners had standing based on proximity

Quotes: ["The court finds that Petitioners have standing to bring this petition for writ of certiorari based on their proximity of Petitioners' property."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Order p.2 contains the quoted standing finding; the rubric truncates it after "property" (the Order adds the nature and scale of the rezoning as a basis).

Excerpt read: p.2: "The court finds that petitioners have standing to bring this petition for writ of certiorari based on their proximity of Petitioners' property (located across the street from the subject rezoning) and the nature and scale of the subject rezoning..."

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx

### Second check: not required


## 6: Order Granting Petition for Writ of Certiorari

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #2 states_in_the_first_assignment_that_the_circuit_court_found_th_2 (source).

Authority type: case; as written: Order.docx at 2; pincite: 2.

Cited for: Court found the BOCC departed from the quasi-judicial record

Quotes: ['[t]he Lee County Board of County Commissioners ("BOCC") improperly departed from the record created at the quasi-judicial hearings held below.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted language appears on Order p.2.

Excerpt read: p.2: "the Lee County Board of County Commissioners (\"BOCC\") improperly departed from the record created at the quasi-judicial hearings held below"

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx

### Second check: not required


## 7: Order Granting Petition for Writ of Certiorari

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #3 states_in_the_first_assignment_that_the_circuit_court_found_th_3 (source).

Authority type: case; as written: Order.docx at 3; pincite: 3.

Cited for: Court found the County's conduct created prejudice and bias

Quotes: ['Lee county further prejudiced the quasi-judicial process ... by its conduct which predetermined, or at very least created prejudice and bias, the decision to approve this quasi-judicial rezoning.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted language appears on Order p.3 (capitalization of "County" aside).

Excerpt read: p.3: "Lee County further prejudiced the quasi-judicial process ... by its conduct which predetermined, or at very least created prejudice and bias, the decision to approve this quasi-judicial rezoning."

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx

### Second check: not required


## 8: Order Granting Petition for Writ of Certiorari

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #4 states_in_the_first_assignment_that_the_circuit_court_found_th_4 (source).

Authority type: case; as written: Order.docx at 5; pincite: 5.

Cited for: Court found FAA regulations were not fully considered

Quotes: ['The decision below violated the essential requirements of law contained in the substantive provisions of the Land Development Code (LDC), adopting by reference "protective" regulatory guidance such as issued by the FAA regulating Land Use and Compatibility Advisories that were not fully considered below.']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Order p.5 reads "contained in the substantive provisions codified in the Land Development Code (LDC)"; the rubric omits "codified". Otherwise verbatim.

Excerpt read: p.5: "The decision below violated the essential requirements of law contained in the substantive provisions codified in the Land Development Code (LDC), adopting by reference \"protective\" regulatory guidance such as issued by the FAA regulating Land Use and Compatibility Advisories that were not fully considered below."

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx

### Second check: not required


## 9: Lee County Administrative Code AC-2-6, s. 4.1.B

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #6 states_in_the_first_assignment_that_under_lee_county_fla_admin_c (criterion).

Authority type: regulation; as written: Lee County, Fla. Admin. Code § 2-6, 4.1 B. (2025); pincite: 4.1 B..

Cited for: DCI2018-10023 was considered withdrawn on February 13, 2020, six months after the August 13, 2019 remand

Quotes: []

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

Admin. Code AC-2-6 s. 4.1 governs "Applications or Appeals Remanded by the Board to the Hearing Examiner," and s. 4.1.B.(1) deems an application withdrawn only if the six-month deadline is missed "because of action or inaction of the Applicant/Appellant." The 2019 remand of DCI2018-10023 (per the Petition) was a joint applicant-staff request granted at the Hearing Examiner stage, sending the case back to staff, not a Board remand to the Hearing Examiner, so the provision does not by its terms deem that case withdrawn on February 13, 2020. The version read was last amended 8/2/22; the version in force in 2019-20 (amended 11/17/15) was not read. The rubric's remand date "August 13, 2029" is a typo for 2019. The quoted sentence itself is accurate.

Excerpt read: "4.1 Applications or Appeals Remanded by the Board to the Hearing Examiner. The following procedures apply to applications or appeals remanded to the Hearing Examiner by the Board: ... B. Remanded hearings must occur within six months of the date the remand order was rendered. (1) If the six month deadline is not met because of action or inaction of the Applicant/Appellant, the application/appeal will be considered withdrawn."

- https://www.leegov.com/bocc/Administrative%20Codes/AC-2-6.pdf

### Second check: MISCHARACTERIZED

The cited AC-2-6 section is expressly limited to Board remands to the Hearing Examiner and conditions deemed withdrawal on applicant-caused delay. The Petition describes a Hearing Examiner remand to staff by joint applicant-staff request. The rubric cannot derive automatic February 2020 withdrawal from this provision. The 2019 version remains unlocated.

Excerpt read: Section 4.1 heading specifies Board-to-Hearing-Examiner remands; subsection B(1) requires delay because of applicant action or inaction.

- https://www.leegov.com/bocc/Administrative%20Codes/AC-2-6.pdf

Model: gpt-6-sol; reasoning effort: high.

## 10: Lee County Administrative Code AC-2-6, s. 4.1.B

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #6 (source).

Authority type: regulation; as written: Lee County, Fla. Admin. Code § 2-6, 4.1 B. (2025); pincite: 4.1 B..

Cited for: Six-month remand deadline renders DCI2018-10023 withdrawn as of February 13, 2020

Quotes: ['If the six month deadline is not met because of action or inaction of the Applicant/Appellant, the application/appeal will be considered withdrawn.']

Context: Remand occurred on August 13, 2029, and six months after that is February 13, 2020.

Fictional by design: False; 

### First check: MISCHARACTERIZED

Admin. Code AC-2-6 s. 4.1 governs "Applications or Appeals Remanded by the Board to the Hearing Examiner," and s. 4.1.B.(1) deems an application withdrawn only if the six-month deadline is missed "because of action or inaction of the Applicant/Appellant." The 2019 remand of DCI2018-10023 (per the Petition) was a joint applicant-staff request granted at the Hearing Examiner stage, sending the case back to staff, not a Board remand to the Hearing Examiner, so the provision does not by its terms deem that case withdrawn on February 13, 2020. The version read was last amended 8/2/22; the version in force in 2019-20 (amended 11/17/15) was not read. The rubric's remand date "August 13, 2029" is a typo for 2019. The quoted sentence itself is accurate.

Excerpt read: "4.1 Applications or Appeals Remanded by the Board to the Hearing Examiner. The following procedures apply to applications or appeals remanded to the Hearing Examiner by the Board: ... B. Remanded hearings must occur within six months of the date the remand order was rendered. (1) If the six month deadline is not met because of action or inaction of the Applicant/Appellant, the application/appeal will be considered withdrawn."

- https://www.leegov.com/bocc/Administrative%20Codes/AC-2-6.pdf

### Second check: MISCHARACTERIZED

Same AC-2-6 mismatch as ref 9: the supplied 2019 case history is a remand to staff at the Hearing Examiner stage, not the Board-to-Hearing-Examiner remand regulated by section 4.1. The historical 2019 code text was not retrieved.

Excerpt read: Section 4.1 concerns applications or appeals remanded by the Board to the Hearing Examiner.

- https://www.leegov.com/bocc/Administrative%20Codes/AC-2-6.pdf

Model: gpt-6-sol; reasoning effort: high.

## 11: Lee County Administrative Code AC-2-6, s. 4.1.B

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #7 states_in_the_first_assignment_that_dci2018_10023_remained_activ (penalty; source).

Authority type: regulation; as written: Lee County Administrative Code 2-6, sec. 4.1 B.; pincite: 4.1 B..

Cited for: Stating that DCI2018-10023 remained active until September 13, 2023 is incorrect because the case was considered withdrawn for missing the six-month remand deadline

Quotes: []

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

Admin. Code AC-2-6 s. 4.1 governs "Applications or Appeals Remanded by the Board to the Hearing Examiner," and s. 4.1.B.(1) deems an application withdrawn only if the six-month deadline is missed "because of action or inaction of the Applicant/Appellant." The 2019 remand of DCI2018-10023 (per the Petition) was a joint applicant-staff request granted at the Hearing Examiner stage, sending the case back to staff, not a Board remand to the Hearing Examiner, so the provision does not by its terms deem that case withdrawn on February 13, 2020. The version read was last amended 8/2/22; the version in force in 2019-20 (amended 11/17/15) was not read. The rubric's remand date "August 13, 2029" is a typo for 2019. The quoted sentence itself is accurate.

Excerpt read: "4.1 Applications or Appeals Remanded by the Board to the Hearing Examiner. The following procedures apply to applications or appeals remanded to the Hearing Examiner by the Board: ... B. Remanded hearings must occur within six months of the date the remand order was rendered. (1) If the six month deadline is not met because of action or inaction of the Applicant/Appellant, the application/appeal will be considered withdrawn."

- https://www.leegov.com/bocc/Administrative%20Codes/AC-2-6.pdf

### Second check: MISCHARACTERIZED

The negative criterion penalizes the record's active-case description using an automatic-withdrawal rule whose triggering remand and applicant-causation elements were not established. This does not independently prove the case was active through September 2023.

Excerpt read: Subsection 4.1.B(1) ties deemed withdrawal to applicant-caused failure to meet the remand deadline.

- https://www.leegov.com/bocc/Administrative%20Codes/AC-2-6.pdf

Model: gpt-6-sol; reasoning effort: high.

## 12: Lee County Ordinance No. 23-28 (CPA2023-00003)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #8 mentions_in_the_first_assignment_that_the_subject_property_was_p (criterion).

Authority type: other; as written: Lee County, Fla. Ordinance 23-28 (2023); pincite: .

Cited for: Subject property was placed into the Public Facilities future land use category of the Lee Plan

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Ordinance 23-28 (CPA2023-00003) amended Lee Plan Map 1-A to redesignate 35.65 acres from DR/GR to Public Facilities; the quoted WHEREAS clause is accurate. The criterion says "the subject property" was placed in Public Facilities, but the ordinance covers only 35.65 of the 112.21 acres, and Resolution Z-23-035 describes the property as in the Public Facilities, DR/GR and Wetlands categories.

Excerpt read: Section Two: "...to redesignate 35.65 acres from the Density Reduction/Ground Water Resource future land use category to the Public Facilities future land use category."

- https://results.leegov.com/Home/DownloadFile/KT0000348490
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx

### Second check: not required


## 13: Lee County Ordinance No. 23-28 (CPA2023-00003)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #8 (source).

Authority type: other; as written: Lee County Fla. Ordinance 23-28 (2023); pincite: .

Cited for: Board adopted CPA2023-00003 amending Lee Plan Map 1-A for the facility

Quotes: ['WHEREAS , the Board held a public hearing for the adoption of the proposed amendment on October 18 , 2023. At that hearing , the Board approved a motion to adopt proposed amendment CPA2023-00003 pertaining to Southeast Advanced Water Reclamation Facility, amending Map 1-A of the Lee Plan , the Future Land Use Map.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted WHEREAS clause appears in Ordinance 23-28.

Excerpt read: "WHEREAS, the Board held a public hearing for the adoption of the proposed amendment on October 18, 2023. At that hearing, the Board approved a motion to adopt proposed amendment CPA2023-00003 pertaining to Southeast Advanced Water Reclamation Facility, amending Map 1-A of the Lee Plan, the Future Land Use Map."

- https://results.leegov.com/Home/DownloadFile/KT0000348490

### Second check: not required


## 14: Broward County v. G.B.V. International, Ltd.

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #9 states_in_the_first_assignment_that_the_effect_of_the_order_gran (penalty; source).

Authority type: case; as written: Broward County v. G.B.V. Int'l, Ltd., 787 So. 2d 838, 845 (Fla. 2001); pincite: 845.

Cited for: On granting certiorari a circuit court may only quash and leave the matter pending below as if no order had been entered; saying the Board's decision is 'overturned' is penalized

Quotes: ['When a circuit court grants certiorari relief, it quashes the order and leaves the matter pending before the lower tribunal as if no order had been entered.']

Context: 

Fictional by design: False; 

### First check: MISQUOTED

The quoted sentence "When a circuit court grants certiorari relief, it quashes the order and leaves the matter pending before the lower tribunal as if no order had been entered" does not appear in G.B.V. (phrase searches for "as if no order had been entered" and "quashes the order" returned no match). The proposition is supported at *844, where G.B.V. block-quotes Tamiami Trail Tours, but in different words and not at 845.

Excerpt read: *844 (quoting Tamiami Trail Tours, 174 So. 451, 454): "When the order is quashed ... it leaves the subject matter, that is, the controversy pending before the tribunal, commission, or administrative authority, as if no order or judgment had been entered..."

- https://www.courtlistener.com/opinion/1882290/broward-county-v-gbv-intern-ltd/

### Second check: MISQUOTED

G.B.V. discusses quashing by quoting Tamiami Trail Tours at reporter page 844. The rubric's purported verbatim sentence is not in that opinion and its page 845 pin is wrong. The underlying quash-and-return proposition is substantially supported.

Excerpt read: At page 844 the court quotes Tamiami on a quashed order leaving the subject matter as if no order had been entered.

- https://app.midpage.ai/document/broward-county-v-gbv-intern-1882290

Model: gpt-6-sol; reasoning effort: high.

## 15: City of Fort Pierce v. Dickerson

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #10 states_in_the_first_assignment_that_the_county_must_stop_constru (penalty; source).

Authority type: case; as written: City of Fort Pierce v. Dickerson, 588 So.2d 1080, 1082 (Fla. 4th DCA 1991); pincite: 1082.

Cited for: Injunctive relief is not available in certiorari review of a quasi-judicial decision

Quotes: ["Since review of the resolution should have been by certiorari, the trial court was without jurisdiction to entertain a complaint for declaratory and injunctive relief and should not have granted the Dickersons' motion for a temporary injunction."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Both quoted passages appear at 588 So. 2d at 1082. Dickerson holds that a quasi-judicial resolution was reviewable only by certiorari, so the trial court lacked jurisdiction over a complaint for declaratory and injunctive relief, and that certiorari review is limited to quashing.

Excerpt read: *1082: "Since review of the resolution should have been by certiorari, the trial court was without jurisdiction to entertain a complaint for declaratory and injunctive relief and should not have granted the Dickersons' motion for a temporary injunction."

- https://www.courtlistener.com/opinion/1767817/city-of-fort-pierce-v-dickerson/

### Second check: not required


## 16: Fla. R. App. P. 9.100(c)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #11 states_in_the_first_assignment_that_the_exclusive_method_of_revi (criterion).

Authority type: court_rule; as written: Fla. R. App. P. 9.100(c) (2025); pincite: 9.100(c).

Cited for: Exclusive method of review of a quasi-judicial decision is a certiorari petition within 30 days

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.100(c) sets a 30-day deadline for petitions for certiorari and petitions to review quasi-judicial action of local government; quoted text matches. Exclusivity of certiorari review of quasi-judicial action is supported by Dickerson and Lee County LDC s. 34-85(a), not by the rule itself.

Excerpt read: "(c) Petitions for Certiorari; Review of NonFinal Agency Action... The following shall be filed within 30 days of rendition of the order to be reviewed: (1) a petition for certiorari; (2) a petition to review quasi-judicial action of agencies, boards, and commissions of local government..."

- https://rules.floridaappellate.com/rule-9-100/
- https://www.courtlistener.com/opinion/1767817/city-of-fort-pierce-v-dickerson/

### Second check: not required


## 17: Fla. R. App. P. 9.100(c)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #11 (source).

Authority type: court_rule; as written: Fla. R. App. P. 9.100(c) (2025); pincite: 9.100(c).

Cited for: 30-day deadline for certiorari petitions to review local quasi-judicial action

Quotes: ['The following shall be filed within 30 days of rendition of the order to be reviewed: (1) a petition for certiorari; (2) a petition to review quasi-judicial action of agencies, boards, and commissions of local government, which action is not directly appealable under any other provision of general law but may be subject to review by certiorari;']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.100(c) sets a 30-day deadline for petitions for certiorari and petitions to review quasi-judicial action of local government; quoted text matches. Exclusivity of certiorari review of quasi-judicial action is supported by Dickerson and Lee County LDC s. 34-85(a), not by the rule itself.

Excerpt read: "(c) Petitions for Certiorari; Review of NonFinal Agency Action... The following shall be filed within 30 days of rendition of the order to be reviewed: (1) a petition for certiorari; (2) a petition to review quasi-judicial action of agencies, boards, and commissions of local government..."

- https://rules.floridaappellate.com/rule-9-100/
- https://www.courtlistener.com/opinion/1767817/city-of-fort-pierce-v-dickerson/

### Second check: not required


## 18: City of Fort Pierce v. Dickerson

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #11 (source).

Authority type: case; as written: City of Fort Pierce v. Dickerson, 588 So.2d 1080, 1082 (Fla. 4th DCA 1991); pincite: 1082.

Cited for: Quasi-judicial decisions reviewable only by certiorari, not by complaint for declaratory/injunctive relief

Quotes: ["Thus, we conclude that the resolution by the Ft. Pierce City Commission was quasi-judicial. Consequently, we agree with Ft. Pierce's assertion that since the resolution was a quasi-judicial decision rendered by the Commission, it was reviewable only by petition for writ of certiorari, and not by a complaint for declaratory and injunctive relief."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Both quoted passages appear at 588 So. 2d at 1082. Dickerson holds that a quasi-judicial resolution was reviewable only by certiorari, so the trial court lacked jurisdiction over a complaint for declaratory and injunctive relief, and that certiorari review is limited to quashing.

Excerpt read: *1082: "Since review of the resolution should have been by certiorari, the trial court was without jurisdiction to entertain a complaint for declaratory and injunctive relief and should not have granted the Dickersons' motion for a temporary injunction."

- https://www.courtlistener.com/opinion/1767817/city-of-fort-pierce-v-dickerson/

### Second check: not required


## 19: Fla. Stat. s. 163.3215(4)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #12 states_in_the_first_assignment_that_the_exclusive_method_of_chal (criterion).

Authority type: statute; as written: Fla. Stat. § 163.3215(4) (2025); pincite: (4).

Cited for: Exclusive method of challenging a development order that materially alters use, density or intensity is a certiorari petition within 30 days

Quotes: []

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

Section 163.3215(4) makes certiorari the sole method only "[i]f a local government elects to adopt or has adopted an ordinance establishing, at a minimum, the requirements listed in this subsection"; otherwise s. 163.3215(1) and (3) provide a de novo action. The rubric quotes from mid-sentence, omitting the condition, and the statute expressly allows injunctive relief to be joined. Lee County LDC s. 34-85(c) preserves actions under s. 163.3215. A search of LDC chs. 2, 10 and 34 for "163.3215" found no subsection (4) opt-in process, only references preserving or channeling challenges to the statute (search limited to those chapters). 2024 statute read.

Excerpt read: "(4) If a local government elects to adopt or has adopted an ordinance establishing, at a minimum, the requirements listed in this subsection, the sole method by which an aggrieved and adversely affected party may challenge any decision of local government granting or denying an application for a development order ... is by an appeal filed by a petition for writ of certiorari ... An action for injunctive or other relief may be joined with the petition for certiorari."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0100-0199/0163/Sections/0163.3215.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: MISCHARACTERIZED

The quoted certiorari-only clause in section 163.3215(4) is conditional on a local ordinance meeting that subsection's requirements. Subsections (1) and (3) otherwise allow a de novo comprehensive-plan consistency action, with injunctive relief available to be joined. A general rule for every development-order challenge is unsupported.

Excerpt read: Subsection (4) begins with the local-government election condition; subsection (3) authorizes de novo action and joined injunctive relief.

- https://www.flsenate.gov/Laws/Statutes/2024/0163.3215

Model: gpt-6-sol; reasoning effort: high.

## 20: Fla. Stat. s. 163.3215(4)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #12 (source).

Authority type: statute; as written: Fla. Stat. 163.3215(4) (2025); pincite: (4).

Cited for: Certiorari in circuit court is the sole method to challenge such a development order

Quotes: ['the sole method by which an aggrieved and adversely affected party may challenge any decision of local government granting or denying an application for a development order ... is by an appeal filed by a petition for writ of certiorari filed in circuit court no later than 30 days following rendition of a development order ... An action for injunctive or other relief may be joined with the petition for certiorari.']

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

Section 163.3215(4) makes certiorari the sole method only "[i]f a local government elects to adopt or has adopted an ordinance establishing, at a minimum, the requirements listed in this subsection"; otherwise s. 163.3215(1) and (3) provide a de novo action. The rubric quotes from mid-sentence, omitting the condition, and the statute expressly allows injunctive relief to be joined. Lee County LDC s. 34-85(c) preserves actions under s. 163.3215. A search of LDC chs. 2, 10 and 34 for "163.3215" found no subsection (4) opt-in process, only references preserving or channeling challenges to the statute (search limited to those chapters). 2024 statute read.

Excerpt read: "(4) If a local government elects to adopt or has adopted an ordinance establishing, at a minimum, the requirements listed in this subsection, the sole method by which an aggrieved and adversely affected party may challenge any decision of local government granting or denying an application for a development order ... is by an appeal filed by a petition for writ of certiorari ... An action for injunctive or other relief may be joined with the petition for certiorari."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0100-0199/0163/Sections/0163.3215.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: MISCHARACTERIZED

The statute itself does not make certiorari universally exclusive. Its subsection (4) opt-in condition is omitted from the rubric's proposition; the County's adoption of a qualifying ordinance was not established.

Excerpt read: Subsection (4) limits its certiorari path to a local government that elects a qualifying ordinance.

- https://www.flsenate.gov/Laws/Statutes/2024/0163.3215

Model: gpt-6-sol; reasoning effort: high.

## 21: Fla. Stat. s. 163.3215(4)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #12 (justification).

Authority type: statute; as written: Fla. Stat. 163.3215(4); pincite: (4).

Cited for: Challenging a development order is the sole method to seek injunctive relief

Quotes: []

Context: This is crucial because challenging a development order is the sole method to seek injunctive relief under Fla. Stat. 163.3215(4).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Section 163.3215(4) makes certiorari the sole method only "[i]f a local government elects to adopt or has adopted an ordinance establishing, at a minimum, the requirements listed in this subsection"; otherwise s. 163.3215(1) and (3) provide a de novo action. The rubric quotes from mid-sentence, omitting the condition, and the statute expressly allows injunctive relief to be joined. Lee County LDC s. 34-85(c) preserves actions under s. 163.3215. A search of LDC chs. 2, 10 and 34 for "163.3215" found no subsection (4) opt-in process, only references preserving or channeling challenges to the statute (search limited to those chapters). 2024 statute read.

Excerpt read: "(4) If a local government elects to adopt or has adopted an ordinance establishing, at a minimum, the requirements listed in this subsection, the sole method by which an aggrieved and adversely affected party may challenge any decision of local government granting or denying an application for a development order ... is by an appeal filed by a petition for writ of certiorari ... An action for injunctive or other relief may be joined with the petition for certiorari."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0100-0199/0163/Sections/0163.3215.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: MISCHARACTERIZED

The statute permits injunctive relief in a de novo action under subsection (3) unless the subsection (4) local opt-in procedure applies. It does not establish that certiorari is the sole route to any injunction. This is confined to statutory comprehensive-plan consistency claims, not all collateral injunction theories.

Excerpt read: Subsection (3) allows a de novo action and permits a request for injunctive relief to be joined.

- https://www.flsenate.gov/Laws/Statutes/2024/0163.3215

Model: gpt-6-sol; reasoning effort: high.

## 22: Fla. Stat. s. 163.3167(10)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #13 states_in_the_first_assignment_that_under_fla_stat_163_3167_10_2 (criterion).

Authority type: statute; as written: Fla. Stat § 163.3167(10) (2025); pincite: (10).

Cited for: The project's development order may not be invalidated by a subsequent judicial determination because the appeal period has expired

Quotes: []

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

Section 163.3167(10)(a) protects a development order only from invalidation by a later judicial determination that the land development regulations themselves are invalid for deficient approval standards; (10)(b) says the subsection does not preclude "a common law writ of certiorari proceeding." It does not shield the project's development order from the consequences of certiorari review of the rezoning, the use the criterion makes of it. Quoted text of (10)(a) is accurate (2024 statute).

Excerpt read: "(10)(a) If a local government grants a development order ... the development order may not be invalidated by a subsequent judicial determination that such land development regulations ... are invalid because of a deficiency in the approval standards. (b) This subsection does not preclude or affect the timely institution of any other remedy available at law or equity, including a common law writ of certiorari proceeding..."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0100-0199/0163/Sections/0163.3167.html

### Second check: MISCHARACTERIZED

Section 163.3167(10)(a) protects an order against later invalidation of land-development regulations for deficient approval standards; it does not immunize this order against direct certiorari review. Subsection (10)(b) expressly preserves common-law certiorari.

Excerpt read: Subsection (10)(a) addresses a subsequent judicial determination about deficient land-development regulations; (10)(b) preserves certiorari.

- https://www.flsenate.gov/Laws/Statutes/2024/163.3167

Model: gpt-6-sol; reasoning effort: high.

## 23: Fla. Stat. s. 163.3167(10)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #13 (source).

Authority type: statute; as written: Fla. Stat 163.3167(10) (2025); pincite: (10).

Cited for: Same

Quotes: ['If a local government grants a development order pursuant to its adopted land development regulations and the order is not the subject of a pending appeal and the timeframe for filing an appeal has expired, the development order may not be invalidated by a subsequent judicial determination that such land development regulations, or any portion thereof that is relevant to the development order, are invalid because of a deficiency in the approval standards']

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

Section 163.3167(10)(a) protects a development order only from invalidation by a later judicial determination that the land development regulations themselves are invalid for deficient approval standards; (10)(b) says the subsection does not preclude "a common law writ of certiorari proceeding." It does not shield the project's development order from the consequences of certiorari review of the rezoning, the use the criterion makes of it. Quoted text of (10)(a) is accurate (2024 statute).

Excerpt read: "(10)(a) If a local government grants a development order ... the development order may not be invalidated by a subsequent judicial determination that such land development regulations ... are invalid because of a deficiency in the approval standards. (b) This subsection does not preclude or affect the timely institution of any other remedy available at law or equity, including a common law writ of certiorari proceeding..."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0100-0199/0163/Sections/0163.3167.html

### Second check: MISCHARACTERIZED

The criterion takes the protection in section 163.3167(10)(a) outside its narrow predicate and ignores (10)(b)'s certiorari savings clause. The quotation of (10)(a) is accurate but the use made of it is not.

Excerpt read: The statute expressly says subsection (10) does not preclude a common-law certiorari proceeding.

- https://www.flsenate.gov/Laws/Statutes/2024/163.3167

Model: gpt-6-sol; reasoning effort: high.

## 24: City of Fort Pierce v. Dickerson

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #14 states_in_the_first_assignment_that_the_petitioners_may_file_a_s (penalty; source).

Authority type: case; as written: City of Fort Pierce v. Dickerson, 588 So.2d 1080, 1082 (Fla. 4th DCA 1991); pincite: 1082.

Cited for: Petitioners cannot bring a separate action for injunction to stop construction

Quotes: ["Since review of the resolution should have been by certiorari, the trial court was without jurisdiction to entertain a complaint for declaratory and injunctive relief and should not have granted the Dickersons' motion for a temporary injunction."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Both quoted passages appear at 588 So. 2d at 1082. Dickerson holds that a quasi-judicial resolution was reviewable only by certiorari, so the trial court lacked jurisdiction over a complaint for declaratory and injunctive relief, and that certiorari review is limited to quashing.

Excerpt read: *1082: "Since review of the resolution should have been by certiorari, the trial court was without jurisdiction to entertain a complaint for declaratory and injunctive relief and should not have granted the Dickersons' motion for a temporary injunction."

- https://www.courtlistener.com/opinion/1767817/city-of-fort-pierce-v-dickerson/

### Second check: not required


## 25: Fla. R. App. P. 9.030(b)(2)(B)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #15 states_in_the_first_assignment_that_the_county_could_appeal_the (criterion).

Authority type: court_rule; as written: Fla. R. App. P. 9.030(b)(2)(B); pincite: 9.030(b)(2)(B).

Cited for: County could seek review of the Order in the Sixth DCA

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.030(b)(2)(B) provides district-court certiorari jurisdiction to review final orders of circuit courts acting in their review capacity; quoted text matches.

Excerpt read: "(2) Certiorari Jurisdiction. The certiorari jurisdiction of district courts of appeal may be sought to review: (A) nonfinal orders of lower tribunals other than as prescribed by rule 9.130; or (B) final orders of circuit courts acting in their review capacity."

- https://rules.floridaappellate.com/rule-9-030/

### Second check: not required


## 26: Fla. R. App. P. 9.030(b)(2)(B)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #15 (source).

Authority type: court_rule; as written: Florida Rule of Appellate Procedure 9.030(b)(2)(B); pincite: 9.030(b)(2)(B).

Cited for: District court certiorari jurisdiction over circuit-court review orders

Quotes: ['(B) final orders of circuit courts acting in their review capacity.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.030(b)(2)(B) provides district-court certiorari jurisdiction to review final orders of circuit courts acting in their review capacity; quoted text matches.

Excerpt read: "(2) Certiorari Jurisdiction. The certiorari jurisdiction of district courts of appeal may be sought to review: (A) nonfinal orders of lower tribunals other than as prescribed by rule 9.130; or (B) final orders of circuit courts acting in their review capacity."

- https://rules.floridaappellate.com/rule-9-030/

### Second check: not required


## 27: Lee County LDC s. 34-83

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #16 states_in_the_first_assignment_that_the_county_could_remand_the (criterion).

Authority type: regulation; as written: Lee County Fla. Land Development Code § 34-83(a)(6) (2025); pincite: 34-83(a)(6).

Cited for: County could remand the case to the Hearing Examiner to address the Order's deficiencies

Quotes: []

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

The quoted remand sentence is LDC s. 34-83(a)(4)a.1.b), not s. 34-83(a)(6). Section 34-83(a)(6) is the separate rule that "If a remand hearing does not occur within six months, the application will be deemed withdrawn." Current text; s. 34-83 last amended by Ord. 22-11 (2022), so it matches the January 1, 2025 version.

Excerpt read: s.34-83(a)(4)a.1.b): "The Board may remand a case back to the Hearing Examiner for further review of specific issues. The scope of the remanded hearing will be limited to the specific issues identified by the Board." (a)(6): "Remand by Board. If a remand hearing does not occur within six months, the application will be deemed withdrawn."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: WRONG_CITATION_REAL_CASE

The quoted Board remand authority appears in LDC 34-83(a)(4)a.1.b, whereas the cited (a)(6) concerns deemed withdrawal after a remand hearing does not occur within six months. The remand proposition itself exists.

Excerpt read: Section (a)(4)a.1.b permits Board remand; (a)(6) gives the six-month withdrawal consequence.

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTIIAD_DIV2BOCOCO_S34-83FUAU

Model: gpt-6-sol; reasoning effort: high.

## 28: Lee County LDC s. 34-83

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #16 (source).

Authority type: regulation; as written: Lee County Fla. Land Development Code § 34-83(a)(6) (2025); pincite: 34-83(a)(6).

Cited for: Board may remand to the Hearing Examiner for specific issues

Quotes: ['The Board may remand a case back to the Hearing Examiner for further review of specific issues. The scope of the remanded hearing will be limited to the specific issues identified by the Board.']

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

The quoted remand sentence is LDC s. 34-83(a)(4)a.1.b), not s. 34-83(a)(6). Section 34-83(a)(6) is the separate rule that "If a remand hearing does not occur within six months, the application will be deemed withdrawn." Current text; s. 34-83 last amended by Ord. 22-11 (2022), so it matches the January 1, 2025 version.

Excerpt read: s.34-83(a)(4)a.1.b): "The Board may remand a case back to the Hearing Examiner for further review of specific issues. The scope of the remanded hearing will be limited to the specific issues identified by the Board." (a)(6): "Remand by Board. If a remand hearing does not occur within six months, the application will be deemed withdrawn."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: WRONG_CITATION_REAL_CASE

The Board's specific-issues remand sentence is in LDC 34-83(a)(4)a.1.b, not the cited (a)(6).

Excerpt read: The two subsections separately address Board remand authority and a six-month remand deadline.

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTIIAD_DIV2BOCOCO_S34-83FUAU

Model: gpt-6-sol; reasoning effort: high.

## 29: Sandra G. Smith, Immunity of State and State Related Activities from Local Municipal Zoning Regulations: Florida Focus

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #19 states_in_the_first_assignment_that_the_county_could_take_the_po (source).

Authority type: restatement_or_treatise; as written: Sandra G. Smith, Immunity of State and State Related Activities from Local Municipal Zoning Regulations: Florida Focus, 28 Fla. L. Rev. 800 (1967); pincite: .

Cited for: County not bound by its own zoning when performing a governmental function

Quotes: ['The Fourth District Court of Appeal relied on Nichols for the premise that in the performance of a governmental activity the county should not be subject to its own zoning restrictions.', 'a governmental entity to place a governmental facility without regard to a comprehensive zoning ordinance or its procedures.']

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

The article PDF is accessible and its quoted historical account is real. Its cover and repository metadata say 1967, but the printed journal header says 1976 and the article cites 1976 decisions; the opening reference to a '1978' decision also conflicts with its 1973 footnote. More materially, its conclusion says Florida had moved away from categorical immunity and that, absent express exemption, a county is subject to its zoning. The rubric's unqualified current-law inference reverses the article's conclusion.

Excerpt read: PDF pages 3-4 contain the quoted Nichols/A1A/Parkway discussion; page 16 concludes that Florida had shifted toward regulation and balancing.

- https://www.floridalawreview.com/article/79428-immunity-of-state-and-state-related-activities-from-local-municipal-zoning-regulations-florida-focus/attachment/165381.pdf

### Second check: pending


## 30: "Nichols" (unidentified; possibly Nichols Engineering & Research Corp. v. State ex rel. Knight, 59 So. 2d 874 (Fla. 1952))

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #19 (source, within quoted article).

Authority type: case; as written: Nichols; pincite: .

Cited for: Authority relied on by the Fourth DCA for county immunity from its own zoning

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

"Nichols" is referenced only inside the rubric's quotation of the Smith article, which I could not read. Parkway Towers (281 So. 2d at 69) cites Nichols Engineering & Research Corp. v. State ex rel. Knight, 59 So. 2d 874 (Fla. 1952), a likely candidate, but the article's referent and its "Fourth District" statement were not confirmed.

Excerpt read: 281 So. 2d at 69: "Nichols Engineering & Research Corp. v. State ex rel. Knight, Fla. 1952, 59 So.2d 874"

- https://www.courtlistener.com/opinion/1672985/metropolitan-dade-cty-v-parkway-towers-condominium-assn/

### Second check: not required


## 31: Metropolitan Dade County v. Parkway Towers Condominium Ass'n

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #19 (source).

Authority type: case; as written: Metropolitan Dade County v. Parkway Towers Condominium Ass'n, 281 So. 2d 68 (Fla. 3d DCA 1973); pincite: .

Cited for: Third DCA case establishing governmental immunity from zoning (rubric says it is not publicly available)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Metropolitan Dade County v. Parkway Towers Condominium Ass'n, 281 So. 2d 68 (Fla. 3d DCA 1973) holds the county may site a governmental facility notwithstanding its zoning absent an affirmative waiver. The opinion is publicly available on CourtListener, contrary to the rubric's note.

Excerpt read: *69: "These authorities recognize that under the common law a governmental entity may place a governmental facility without regard to a comprehensive zoning ordinance or its procedures." *70: "...the County has the right to erect a governmental facility ... notwithstanding the use classification of any particular site."

- https://www.courtlistener.com/opinion/1672985/metropolitan-dade-cty-v-parkway-towers-condominium-assn/

### Second check: not required


## 32: Parkway Towers Condominium Ass'n v. Metropolitan Dade County

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #19 (source).

Authority type: case; as written: Parkway Towers Con. Ass'n v. Metropolitan Dade Cnty., 295 So.2d 295 (Fla. 1974); pincite: 295-96.

Cited for: Supreme Court's prospective view that rezoning should precede county facilities is dicta because the court upheld the district court on immunity

Quotes: ['Although we now consider our issuance of the writ of certiorari to have been improvident in this case, which results in our discharge thereof, it is nevertheless our view prospectively that zoning variations to accommodate county or municipal facility purposes should either have been anticipated in zoning ordinances before construction or operation of such facilities is commenced *296 or, if this has not been done, construction should not be undertaken thereof until after due modification or change therefor is made in existing zoning ordinances.']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Quote is accurate (295-96). The rubric says the Supreme Court "upheld the district court's decision on immunity"; the Court in fact discharged the writ as improvidently granted for lack of direct conflict, leaving the district court decision in place without reaching the merits.

Excerpt read: "...we are of the opinion that there is no direct conflict justifying our taking certiorari conflict jurisdiction to review the decision of the District Court of Appeal... The writ is discharged and it is so ordered."

- https://www.courtlistener.com/opinion/1934327/parkway-towers-con-assn-v-metropolitan-dade-cty/

### Second check: not required


## 33: Fla. R. App. P. 9.030(b)(2)(B)

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #22 states_in_the_first_assignment_that_the_county_should_file_a_tim (source).

Authority type: court_rule; as written: Florida Rule of Appellate Procedure 9.030(b)(2)(B); pincite: 9.030(b)(2)(B).

Cited for: Appeal to the Sixth DCA by certiorari

Quotes: ['(B) final orders of circuit courts acting in their review capacity.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.030(b)(2)(B) provides district-court certiorari jurisdiction to review final orders of circuit courts acting in their review capacity; quoted text matches.

Excerpt read: "(2) Certiorari Jurisdiction. The certiorari jurisdiction of district courts of appeal may be sought to review: (A) nonfinal orders of lower tribunals other than as prescribed by rule 9.130; or (B) final orders of circuit courts acting in their review capacity."

- https://rules.floridaappellate.com/rule-9-030/

### Second check: not required


## 34: Lee County LDC s. 34-83

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #23 states_in_the_first_assignment_that_the_county_should_remand_the (source).

Authority type: regulation; as written: Lee County Fla. Land Development Code § 34-83(a)(6) (2025); pincite: 34-83(a)(6).

Cited for: Board may remand to the Hearing Examiner while an appeal is pending

Quotes: ['The Board may remand a case back to the Hearing Examiner for further review of specific issues. The scope of the remanded hearing will be limited to the specific issues identified by the Board.']

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

The quoted remand sentence is LDC s. 34-83(a)(4)a.1.b), not s. 34-83(a)(6). Section 34-83(a)(6) is the separate rule that "If a remand hearing does not occur within six months, the application will be deemed withdrawn." Current text; s. 34-83 last amended by Ord. 22-11 (2022), so it matches the January 1, 2025 version.

Excerpt read: s.34-83(a)(4)a.1.b): "The Board may remand a case back to the Hearing Examiner for further review of specific issues. The scope of the remanded hearing will be limited to the specific issues identified by the Board." (a)(6): "Remand by Board. If a remand hearing does not occur within six months, the application will be deemed withdrawn."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: WRONG_CITATION_REAL_CASE

LDC 34-83(a)(4)a.1.b supports Board remand to the Hearing Examiner; (a)(6) is the six-month hearing/withdrawal provision. The source pin is wrong even though the basic remand power exists.

Excerpt read: The Board-remand language and deadline language are in different numbered subsections.

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTIIAD_DIV2BOCOCO_S34-83FUAU

Model: gpt-6-sol; reasoning effort: high.

## 35: Parkway Towers Condominium Ass'n v. Metropolitan Dade County

Document: assignment-1 rubric.json; location: assignment-1 rubric criterion #24 states_in_the_first_assignment_that_the_county_should_cease_cons (penalty; source).

Authority type: case; as written: Parkway Towers Con. Ass'n v. Metropolitan Dade Cty., 295 So.2d 295 (Fla. 1974); pincite: 295.

Cited for: Supreme Court declined to delay construction of a public project over zoning

Quotes: ['...This being so, we feel no useful or practical purpose would be served in interrupting and delaying the construction until a zoning change is effected retroactively ... To interrupt the construction now would cause needless expense and damage with no prospect or likelihood that the Commission would reach a different final result.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Both quoted passages appear in Parkway Towers, 295 So. 2d at 295-96 (per curiam discharging the writ). The court declined to interrupt construction of a county facility.

Excerpt read: "To interrupt the construction now would cause needless expense and damage with no prospect or likelihood that the Commission would reach a different final result." ... "Although we now consider our issuance of the writ of certiorari to have been improvident in this case, which results in our discharge thereof..."

- https://www.courtlistener.com/opinion/1934327/parkway-towers-con-assn-v-metropolitan-dade-cty/

### Second check: not required


## 36: Fla. R. App. P. 9.030(b)(2)(B)

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #0 identifies_in_the_second_assignment_that_the_appropriate_mechani (source).

Authority type: court_rule; as written: Florida Rule of Appellate Procedure 9.030(b)(2)(B); pincite: 9.030(b)(2)(B).

Cited for: Second-tier review is by certiorari petition to the Sixth DCA

Quotes: ['(B) final orders of circuit courts acting in their review capacity.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.030(b)(2)(B) provides district-court certiorari jurisdiction to review final orders of circuit courts acting in their review capacity; quoted text matches.

Excerpt read: "(2) Certiorari Jurisdiction. The certiorari jurisdiction of district courts of appeal may be sought to review: (A) nonfinal orders of lower tribunals other than as prescribed by rule 9.130; or (B) final orders of circuit courts acting in their review capacity."

- https://rules.floridaappellate.com/rule-9-030/

### Second check: not required


## 37: Dusseau v. Metropolitan Dade County Board of County Commissioners

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #1 states_in_the_second_assignment_that_the_circuit_court_erred_by (criterion).

Authority type: case; as written: Dusseau v. Metro. Dade Cnty. Bd. of Cnty. Comm'rs, 794 So.2d 1270 (Fla. 2001); pincite: .

Cited for: Circuit court erred by ignoring competent substantial evidence supporting approval

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

All quoted passages appear in Dusseau at 1275-76 (and the first sentence also appears in G.B.V. at 846). Dusseau supports the stated limits on first-tier review.

Excerpt read: *1275-76: "We reiterate that the 'competent substantial evidence' standard cannot be used by a reviewing court as a mechanism for exerting covert control over the policy determinations ... As long as the record contains competent substantial evidence to support the agency's decision, the decision is presumed lawful and the court's job is ended."

- https://www.courtlistener.com/opinion/1859830/dusseau-v-metro-dade-co-bd-of-comrs/

### Second check: not required


## 38: Dusseau v. Metropolitan Dade County Board of County Commissioners

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #1 (source).

Authority type: case; as written: Dusseau v. Metro. Dade Cnty. Bd. of Cnty. Comm'rs, 794 So.2d 1270 (Fla. 2001); pincite: .

Cited for: Limits of first-tier certiorari review; court may not reweigh evidence

Quotes: ["Notably, when applying the third prong, the court should review the record to determine simply whether the Commission's decision is supported by competent substantial evidence.", 'We reiterate that the "competent substantial evidence" standard cannot be used by a reviewing court as a mechanism for exerting covert control over the policy determinations and factual findings of the local agency.', "As long as the record contains competent substantial evidence to support the agency's decision, the decision is presumed lawful and the court's job is ended."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

All quoted passages appear in Dusseau at 1275-76 (and the first sentence also appears in G.B.V. at 846). Dusseau supports the stated limits on first-tier review.

Excerpt read: *1275-76: "We reiterate that the 'competent substantial evidence' standard cannot be used by a reviewing court as a mechanism for exerting covert control over the policy determinations ... As long as the record contains competent substantial evidence to support the agency's decision, the decision is presumed lawful and the court's job is ended."

- https://www.courtlistener.com/opinion/1859830/dusseau-v-metro-dade-co-bd-of-comrs/

### Second check: not required


## 39: City of Deerfield Beach v. Vaillant

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #1 (source, within Dusseau quotation).

Authority type: case; as written: the third prong of Vaillant; pincite: .

Cited for: Vaillant's three-pronged first-tier standard

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The third prong of Vaillant (competent substantial evidence) is the reference in the Dusseau passage the rubric quotes.

Excerpt read: Dusseau *1276: "The court's task vis-a-vis the third prong of Vaillant is simple..."

- https://www.courtlistener.com/opinion/1914497/city-of-deerfield-beach-v-vaillant/
- https://www.courtlistener.com/opinion/1859830/dusseau-v-metro-dade-co-bd-of-comrs/

### Second check: not required


## 40: City of Hialeah Gardens v. Miami-Dade Charter Foundation, Inc.

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #2 states_in_the_second_assignment_that_the_staff_report_recommendi (source).

Authority type: case; as written: City of Hialeah Gardens v. Miami-Dade Charter Found., Inc., 857 So.2d 202, 204-5 (Fla. 3d DCA 2003); pincite: 204-05.

Cited for: The staff report recommending approval is competent substantial evidence supporting the Board's approval

Quotes: ['Here, the testifying staff members utilized their professional experiences and personal observations, as well as Machado\'s application, site plan, and traffic study, as the basis for their testimony. These record materials, along with the staff presentations, combined to provide evidence "sufficiently relevant and material that a reasonable mind would accept it as adequate to support the conclusion reached."']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted passage appears at 857 So. 2d at 205 (within cited 204-05). Hialeah Gardens holds that city staff members' fact-based testimony, with record materials such as the application and site plan, constituted competent substantial evidence, and that relevant fact-based statements, expert or not, must be considered.

Excerpt read: *205: "Here, the testifying staff members utilized their professional experiences and personal observations, as well as Machado's application, site plan, and traffic study, as the basis for their testimony. These record materials, along with the staff presentations, combined to provide evidence 'sufficiently relevant and material that a reasonable mind would accept it as adequate to support the conclusion reached.'"

- https://www.courtlistener.com/opinion/1931203/city-of-hialeah-gardens-v-miami-dade-charter-foundation-inc/

### Second check: not required


## 41: Dusseau v. Metropolitan Dade County Board of County Commissioners

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #2 (justification).

Authority type: case; as written: Dusseau v. Metro. Dade Cnty. Bd. of Cnty. Comm'rs, 794 So.2d 1270 (Fla. 2001); pincite: .

Cited for: Standard of review the circuit court failed to apply

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Dusseau limits first-tier review to whether competent substantial evidence supports the agency decision; the justification's description is accurate.

Excerpt read: *1276: "Evidence contrary to the agency's decision is outside the scope of the inquiry at this point, for the reviewing court above all cannot reweigh the 'pros and cons' of conflicting evidence."

- https://www.courtlistener.com/opinion/1859830/dusseau-v-metro-dade-co-bd-of-comrs/

### Second check: not required


## 42: City of Hialeah Gardens v. Miami-Dade Charter Foundation, Inc.

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #3 states_in_the_second_assignment_that_expert_testimony_on_the_rec (source).

Authority type: case; as written: City of Hialeah Gardens v. Miami-Dade Charter Found., Inc., 857 So.2d 202, 204-5 (Fla. 3d DCA 2003); pincite: 204-05.

Cited for: Expert testimony in the record is competent substantial evidence supporting the Board's approval

Quotes: ['Here, the testifying staff members utilized their professional experiences and personal observations, as well as Machado\'s application, site plan, and traffic study, as the basis for their testimony. These record materials, along with the staff presentations, combined to provide evidence "sufficiently relevant and material that a reasonable mind would accept it as adequate to support the conclusion reached."']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted passage appears at 857 So. 2d at 205 (within cited 204-05). Hialeah Gardens holds that city staff members' fact-based testimony, with record materials such as the application and site plan, constituted competent substantial evidence, and that relevant fact-based statements, expert or not, must be considered.

Excerpt read: *205: "Here, the testifying staff members utilized their professional experiences and personal observations, as well as Machado's application, site plan, and traffic study, as the basis for their testimony. These record materials, along with the staff presentations, combined to provide evidence 'sufficiently relevant and material that a reasonable mind would accept it as adequate to support the conclusion reached.'"

- https://www.courtlistener.com/opinion/1931203/city-of-hialeah-gardens-v-miami-dade-charter-foundation-inc/

### Second check: not required


## 43: Dusseau v. Metropolitan Dade County Board of County Commissioners

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #3 (justification).

Authority type: case; as written: Dusseau v. Metro. Dade Cnty. Bd. of Cnty. Comm'rs, 794 So.2d 1270 (Fla. 2001); pincite: .

Cited for: Standard of review the circuit court failed to apply

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Dusseau limits first-tier review to whether competent substantial evidence supports the agency decision; the justification's description is accurate.

Excerpt read: *1276: "Evidence contrary to the agency's decision is outside the scope of the inquiry at this point, for the reviewing court above all cannot reweigh the 'pros and cons' of conflicting evidence."

- https://www.courtlistener.com/opinion/1859830/dusseau-v-metro-dade-co-bd-of-comrs/

### Second check: not required


## 44: City of Hialeah Gardens v. Miami-Dade Charter Foundation, Inc.

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #4 states_in_the_second_assignment_that_the_hearing_examiner_s_reco (source).

Authority type: case; as written: City of Hialeah Gardens v. Miami-Dade Charter Found., Inc., 857 So.2d 202, 204-5 (Fla. 3d DCA 2003); pincite: 204-05.

Cited for: The Hearing Examiner's recommendation of approval is competent substantial evidence supporting the Board's approval

Quotes: ['Here, the testifying staff members utilized their professional experiences and personal observations, as well as Machado\'s application, site plan, and traffic study, as the basis for their testimony. These record materials, along with the staff presentations, combined to provide evidence "sufficiently relevant and material that a reasonable mind would accept it as adequate to support the conclusion reached."']

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

Hialeah Gardens concerns staff testimony and record materials before a city council; it says nothing about a hearing examiner's recommendation being competent substantial evidence. The quoted passage (accurate at 205) does not support the proposition the criterion cites it for.

Excerpt read: *205: "Here, the testifying staff members utilized their professional experiences and personal observations ... These record materials, along with the staff presentations, combined to provide evidence..." (no reference to a hearing examiner).

- https://www.courtlistener.com/opinion/1931203/city-of-hialeah-gardens-v-miami-dade-charter-foundation-inc/

### Second check: MISCHARACTERIZED

Hialeah Gardens recognizes competent substantial evidence in staff testimony and the record before the council. It does not hold that a Hearing Examiner's recommendation is itself competent substantial evidence, as the criterion asserts.

Excerpt read: The opinion discusses staff testimony, expert material, and the city council's record; no Hearing Examiner recommendation rule appears.

- https://openjurist.org/857/so2d/202/city-of-hialeah-gardens-v-miami-dade-foundation-inc-1931203

Model: gpt-6-sol; reasoning effort: high.

## 45: Dusseau v. Metropolitan Dade County Board of County Commissioners

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #4 (justification).

Authority type: case; as written: Dusseau v. Metro. Dade Cnty. Bd. of Cnty. Comm'rs, 794 So.2d 1270 (Fla. 2001); pincite: .

Cited for: Standard of review the circuit court failed to apply

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Dusseau limits first-tier review to whether competent substantial evidence supports the agency decision; the justification's description is accurate.

Excerpt read: *1276: "Evidence contrary to the agency's decision is outside the scope of the inquiry at this point, for the reviewing court above all cannot reweigh the 'pros and cons' of conflicting evidence."

- https://www.courtlistener.com/opinion/1859830/dusseau-v-metro-dade-co-bd-of-comrs/

### Second check: not required


## 46: Martin County v. Yusem

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #5 states_in_the_second_assignment_that_the_circuit_court_erred_b_2 (source).

Authority type: case; as written: Martin County v. Yusem, 690 So. 2d 1288, 1295 (Fla. 1997); pincite: 1295.

Cited for: Fairly debatable standard applies to the county's decision to construct a water treatment plant on its own property as a legislative act

Quotes: ['The fairly debatable standard of review is a highly deferential standard requiring approval of a planning action if reasonable persons could differ as to its propriety.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted sentence appears at 690 So. 2d at 1295. Yusem holds comprehensive plan amendments are legislative and reviewed under the fairly debatable standard; whether a county's own-property rezoning is legislative is the rubric's argument, not Yusem's holding.

Excerpt read: *1295: "The fairly debatable standard of review is a highly deferential standard requiring approval of a planning action if reasonable persons could differ as to its propriety."

- https://www.courtlistener.com/opinion/1136999/martin-county-v-yusem/

### Second check: not required


## 47: Modlin v. City of Miami Beach

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #5 (source).

Authority type: case; as written: Modlin v. City of Miami Beach, 201 So.2d 70 (Fla. 1967); pincite: .

Cited for: Distinction between legislative and executive/judicial action

Quotes: ['The distinction between legislative action, on the one hand, and executive and judicial action, on the other, is not difficult to define. ... legislative action prescribes a general rule for future operation, whereas judicial and executive action is typically concerned with applying the general rule to specific situations or persons.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted passage appears at 201 So. 2d at 73 (no pin given). Modlin is a tort-immunity case; the passage distinguishes legislative from executive and judicial action as described.

Excerpt read: *73: "The distinction between legislative action, on the one hand, and executive and judicial action, on the other, is not difficult to define. It is sufficient for present purposes to say that the former is typically prospective and nondiscriminatory, whereas the latter operate retroactively and discriminatorily..."

- https://www.courtlistener.com/opinion/1616617/modlin-v-city-of-miami-beach/

### Second check: not required


## 48: Martin County v. Yusem

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #7 states_in_the_second_assignment_that_the_circuit_court_erred_b_3 (source).

Authority type: case; as written: Martin County v. Yusem, 690 So. 2d 1288, 1295 (Fla. 1997); pincite: 1295.

Cited for: Fairly debatable standard applies to the county's decision to enter the Kingston Settlement as a legislative act

Quotes: ['The fairly debatable standard of review is a highly deferential standard requiring approval of a planning action if reasonable persons could differ as to its propriety.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted sentence appears at 690 So. 2d at 1295. Yusem holds comprehensive plan amendments are legislative and reviewed under the fairly debatable standard; whether a county's own-property rezoning is legislative is the rubric's argument, not Yusem's holding.

Excerpt read: *1295: "The fairly debatable standard of review is a highly deferential standard requiring approval of a planning action if reasonable persons could differ as to its propriety."

- https://www.courtlistener.com/opinion/1136999/martin-county-v-yusem/

### Second check: not required


## 49: Modlin v. City of Miami Beach

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #7 (source).

Authority type: case; as written: Modlin v. City of Miami Beach, 201 So.2d 70 (Fla. 1967); pincite: .

Cited for: Distinction between legislative and executive/judicial action

Quotes: ['The distinction between legislative action, on the one hand, and executive and judicial action, on the other, is not difficult to define. ... legislative action prescribes a general rule for future operation, whereas judicial and executive action is typically concerned with applying the general rule to specific situations or persons.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted passage appears at 201 So. 2d at 73 (no pin given). Modlin is a tort-immunity case; the passage distinguishes legislative from executive and judicial action as described.

Excerpt read: *73: "The distinction between legislative action, on the one hand, and executive and judicial action, on the other, is not difficult to define. It is sufficient for present purposes to say that the former is typically prospective and nondiscriminatory, whereas the latter operate retroactively and discriminatorily..."

- https://www.courtlistener.com/opinion/1616617/modlin-v-city-of-miami-beach/

### Second check: not required


## 50: Williams v. Public Utility Protective League

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #7 (source).

Authority type: case; as written: Williams v. Public Util. Protective League, 178 So. 286 (Fla. 1938); pincite: .

Cited for: Power to settle litigation is incident to power to sue and be sued and will not be restrained on speculative fears

Quotes: ['As an abstract proposition of law, the power of the City to compromise, settle, and compose litigation of any kind to which it is a party is an incident to and implied from its power to sue and be sued.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted passage appears verbatim in Williams v. Public Utility Protective League, 178 So. 286, 130 Fla. 603 (Fla. 1938).

Excerpt read: "As an abstract proposition of law, the power of the City to compromise, settle, and compose litigation of any kind to which it is a party is an incident to and implied from its power to sue and be sued. Like the power to legislate and negotiate it will not be restrained..."

- https://www.courtlistener.com/opinion/3402391/williams-v-public-utility-protective-league/

### Second check: not required


## 51: Lee County LDC s. 2-191

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #6 states_in_the_second_assignment_that_the_circuit_court_erred_in (criterion).

Authority type: regulation; as written: Lee County Fla. Land Development Code § 2-191 (2025); pincite: .

Cited for: Communications with staff are not ex parte communications

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 2-191(b) is headed "Unauthorized communications with a County Commissioner prohibited" and (b)(2) contains the quoted employee exception. Last amended by Ord. 22-11 (May 17, 2022), so the text is unchanged since before the documents and January 1, 2025.

Excerpt read: "(b) Unauthorized communications with a County Commissioner prohibited. ... (2) This section does not prohibit the informational discussion of pending or proposed cases or appeals by and between a County Commissioner and any employee of the Board of County Commissioners."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH2AD_ARTVUNCO_S2-191PRLIUNCO

### Second check: not required


## 52: Lee County LDC s. 2-191

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #6 (source).

Authority type: regulation; as written: Lee County Fla. Land Development Code § 2-191 (2025); pincite: 2-191(b)(2).

Cited for: Informational discussions between Commissioners and County employees are not prohibited

Quotes: ['Unauthorized communications with a County Commissioner prohibited. . . . This section does not prohibit the informational discussion of pending or proposed cases or appeals by and between a County Commissioner and any employee of the Board of County Commissioners.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 2-191(b) is headed "Unauthorized communications with a County Commissioner prohibited" and (b)(2) contains the quoted employee exception. Last amended by Ord. 22-11 (May 17, 2022), so the text is unchanged since before the documents and January 1, 2025.

Excerpt read: "(b) Unauthorized communications with a County Commissioner prohibited. ... (2) This section does not prohibit the informational discussion of pending or proposed cases or appeals by and between a County Commissioner and any employee of the Board of County Commissioners."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH2AD_ARTVUNCO_S2-191PRLIUNCO

### Second check: not required


## 53: Fla. Stat. s. 286.0115(3)

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #6 (source).

Authority type: statute; as written: Fla. Stat § 286.0115(3) (2025); pincite: (3).

Cited for: Statute does not restrict local rules on contacts with officials

Quotes: ['This section does not restrict the authority of any board or commission to establish rules or procedures governing public hearings or contacts with local public officials.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Section 286.0115(3) quoted accurately (2024).

Excerpt read: "(3) This section does not restrict the authority of any board or commission to establish rules or procedures governing public hearings or contacts with local public officials."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0200-0299/0286/Sections/0286.0115.html

### Second check: not required


## 54: FAA Advisory Circular 150/5190-7, Minimum Standards for Commercial Aeronautical Activities

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 states_in_the_second_assignment_that_the_circuit_court_erred_b_4 (criterion).

Authority type: other; as written: Fed. Aviation Admin., Advisory Circular No. 150/5190-7, Minimum Standards for Commercial Aeronautical Activities (Dec. 7, 2023); pincite: .

Cited for: The AC the circuit court found incorporated into LDC s. 34-1102

Quotes: []

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

The Order never names AC 150/5190-7 or any minimum-standards AC; it relies on FAA "Land Use and Compatibility Advisories" and "Airport Compatibility, Wildlife Hazard FAA Advisories" (the Petition's AC 150/5190-4B and AC 150/5200-33C). The citation is also garbled: AC 150/5190-7 is dated August 28, 2006 and is cancelled; December 7, 2023 is the date of its replacement, AC 150/5190-8.

Excerpt read: AC 150/5190-7 p.1: "Subject: MINIMUM STANDARDS FOR COMMERCIAL AERONAUTICAL ACTIVITIES Date: August 28, 2006 AC No: 150/5190-7"; FAA current list: "150/5190-8 ... Minimum Standards for Commercial Aeronautical Activities ... 2023-12-07"; Order p.6: "Airport Compatibility, Wildlife Hazard FAA Advisories (Petition 37-59)".

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_7.pdf
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3

### Second check: MISCHARACTERIZED

The supplied Order does not cite AC 150/5190-7. The FAA's primary circular identifies 5190-7 as its cancelled 2006 predecessor and 5190-8 as the December 2023 replacement. The criterion conflates number, date, and what the court addressed.

Excerpt read: The FAA circular's cover gives 5190-8's December 7, 2023 date and cancellation of 5190-7; Order pages 5-6 discuss land-use and wildlife-hazard advisories.

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC-150-5190-8-minimum-standards.pdf

Model: gpt-6-sol; reasoning effort: high.

## 55: Lee County LDC s. 34-1102

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (criterion).

Authority type: regulation; as written: Lee County Fla. Land Development Code § 34-1102 (2025); pincite: .

Cited for: Section does not incorporate AC 150/5190-7

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 34-1102 does not mention AC 150/5190-7 or 150/5190-8 (minimum standards for commercial aeronautical activities); the criterion's premise about the section's content is consistent with its text.

Excerpt read: "...FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced, and 150/5200-33B, as amended, renumbered or replaced..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 56: FAA Advisory Circular 150/5190-7

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source).

Authority type: other; as written: Fed. Aviation Admin., Advisory Circular 150/5190-7 Minimum Standards for Commercial Aeronautical Activities (Dec. 7, 2023); pincite: .

Cited for: Circuit court found the County failed to comply with this AC's airport-compatibility requirements

Quotes: []

Context: The circuit court found that the County had failed to comply with Fed. Aviation Admin., Advisory Circular 150/5190-7 ... requirements for airport compatibility

Fictional by design: False; 

### First check: MISCHARACTERIZED

The Order never names AC 150/5190-7 or any minimum-standards AC; it relies on FAA "Land Use and Compatibility Advisories" and "Airport Compatibility, Wildlife Hazard FAA Advisories" (the Petition's AC 150/5190-4B and AC 150/5200-33C). The citation is also garbled: AC 150/5190-7 is dated August 28, 2006 and is cancelled; December 7, 2023 is the date of its replacement, AC 150/5190-8.

Excerpt read: AC 150/5190-7 p.1: "Subject: MINIMUM STANDARDS FOR COMMERCIAL AERONAUTICAL ACTIVITIES Date: August 28, 2006 AC No: 150/5190-7"; FAA current list: "150/5190-8 ... Minimum Standards for Commercial Aeronautical Activities ... 2023-12-07"; Order p.6: "Airport Compatibility, Wildlife Hazard FAA Advisories (Petition 37-59)".

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_7.pdf
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3

### Second check: MISCHARACTERIZED

The Order's compatibility/wildlife discussion contains no finding that the County violated AC 150/5190-7 minimum standards; the cited date belongs to replacement 5190-8.

Excerpt read: FAA 5190-8 cover identifies 5190-7 as cancelled; Order pages 5-6 do not name either circular.

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC-150-5190-8-minimum-standards.pdf

Model: gpt-6-sol; reasoning effort: high.

## 57: Lee County LDC s. 34-1102

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source).

Authority type: regulation; as written: Lee County, Fla. Land Development Code § 34-1102 (2025); pincite: .

Cited for: Section incorporates only ACs 150/5300-13B and 150/5200-30D

Quotes: []

Context: Lee County, Fla. Land Development Code § 34-1102 (2025) incorporates only Fed. Aviation Admin., Advisory Circular No. 150/5300-13B, Airport Design (2022) and 150/5200-30D ... not ... 150/5190-7

Fictional by design: False; 

### First check: MISCHARACTERIZED

The rubric says s. 34-1102 incorporates only AC 150/5300-13B and AC 150/5200-30D (Airport Field Condition Assessments and Winter Operations Safety). The section names 150/5300-13A (replaced by 13B) and 150/5200-33B (Hazardous Wildlife Attractants, replaced by 33C), not 150/5200-30D; the rubric's own block quote shows 33B. The wildlife-attractant AC is the one the Order and Petition rely on.

Excerpt read: "...FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced, and 150/5200-33B, as amended, renumbered or replaced, which address height obstructions, airport hazards, wildlife attractants..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3

### Second check: MISCHARACTERIZED

LDC 34-1102 names AC 150/5300-13A and AC 150/5200-33B, with replacement language. It does not name 150/5200-30D. The rubric's own quoted section shows the wildlife-attractant 33B citation, making its contrary explanation demonstrably wrong.

Excerpt read: Section 34-1102 lists 150/5300-13A and 150/5200-33B, as amended or replaced.

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

Model: gpt-6-sol; reasoning effort: high.

## 58: FAA Advisory Circular 150/5300-13B, Airport Design

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source).

Authority type: other; as written: Fed. Aviation Admin., Advisory Circular No. 150/5300-13B, Airport Design (2022); pincite: .

Cited for: Incorporated into LDC s. 34-1102

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

AC 150/5300-13B, Airport Design (2022; Change 1, 2024) is the current airport design AC and replaced 150/5300-13A, which LDC s. 34-1102 names "as amended, renumbered or replaced."

Excerpt read: Current list: "150/5300-13B, AAS-100, Airport Design - Change 1"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: UNABLE_TO_VERIFY

The first reviewer read the FAA current/cancelled index and related code incorporation, but expressly did not read this circular's primary text. Identity evidence does not meet this audit's primary-text requirement for a verified citation. Original first-check explanation: AC 150/5300-13B, Airport Design (2022; Change 1, 2024) is the current airport design AC and replaced 150/5300-13A, which LDC s. 34-1102 names "as amended, renumbered or replaced."

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: Current list: "150/5300-13B, AAS-100, Airport Design - Change 1"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 59: FAA Advisory Circular 150/5200-30D, Airport Field Condition Assessments and Winter Operations Safety

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source).

Authority type: other; as written: 150/5200-30D Airport Field Condition Assessments and Winter Operations Safety (July 29, 2016); pincite: .

Cited for: Incorporated into LDC s. 34-1102

Quotes: []

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

AC 150/5200-30D (Airport Field Condition Assessments and Winter Operations Safety, July 29, 2016; Change 2, 2020) exists, but LDC s. 34-1102 does not name or incorporate it; the section names 150/5200-33B (wildlife attractants).

Excerpt read: Current list: "150/5200-30D ... Airport Field Condition Assessments and Winter Operations Safety"; LDC 34-1102: "...and 150/5200-33B, as amended, renumbered or replaced..."

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: MISCHARACTERIZED

FAA AC 150/5200-30D is a real winter-operations circular, but LDC 34-1102 incorporates the wildlife-attractant 150/5200-33B series instead. The rubric's incorporation claim is false.

Excerpt read: FAA 30D title concerns airport field condition and winter operations; LDC 34-1102 names 33B.

- https://www.faa.gov/documentlibrary/media/advisory_circular/150-5200-30d.pdf
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

Model: gpt-6-sol; reasoning effort: high.

## 60: FAA Advisory Circular 150/5190-7

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source).

Authority type: other; as written: Fed. Aviation Admin., Advisory CircularNo. 150/5190-7, Minimum Standards for Commercial Aeronautical Activities (Dec. 7, 2023); pincite: .

Cited for: The AC the Order treats as controlling

Quotes: []

Context: ...not Fed. Aviation Admin., Advisory CircularNo. 150/5190-7, Minimum Standards for Commercial Aeronautical Activities (Dec. 7, 2023), which the order treats as controlling.

Fictional by design: False; 

### First check: MISCHARACTERIZED

The Order never names AC 150/5190-7 or any minimum-standards AC; it relies on FAA "Land Use and Compatibility Advisories" and "Airport Compatibility, Wildlife Hazard FAA Advisories" (the Petition's AC 150/5190-4B and AC 150/5200-33C). The citation is also garbled: AC 150/5190-7 is dated August 28, 2006 and is cancelled; December 7, 2023 is the date of its replacement, AC 150/5190-8.

Excerpt read: AC 150/5190-7 p.1: "Subject: MINIMUM STANDARDS FOR COMMERCIAL AERONAUTICAL ACTIVITIES Date: August 28, 2006 AC No: 150/5190-7"; FAA current list: "150/5190-8 ... Minimum Standards for Commercial Aeronautical Activities ... 2023-12-07"; Order p.6: "Airport Compatibility, Wildlife Hazard FAA Advisories (Petition 37-59)".

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_7.pdf
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3

### Second check: MISCHARACTERIZED

The Order neither names nor treats AC 150/5190-7 as controlling; its airport analysis concerns compatibility and wildlife hazards. The FAA 5190-8 document confirms that the rubric also attached the replacement's 2023 date to the old circular.

Excerpt read: Order pages 5-6 use land-use and wildlife-hazard descriptions; the FAA circular identifies the replacement and cancellation dates.

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC-150-5190-8-minimum-standards.pdf

Model: gpt-6-sol; reasoning effort: high.

## 61: Lee County LDC s. 34-1102

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source).

Authority type: regulation; as written: Lee County, Fla. Land Development Code § 34-1102 (2025); [municode URL]; pincite: .

Cited for: Text of the purpose clause

Quotes: ['The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chs. 330 and 333, as amended, as well as Federal regulations, as amended, including 14 CFR Parts 77, 150 and 151 and FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced, and 150/5200-33B, as amended, renumbered or replaced...']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted purpose clause matches current LDC s. 34-1102 (last amended Ord. 19-03, 2019, so unchanged on January 1, 2025); "F.S. Chapters" vs "F.S. Chs." is immaterial.

Excerpt read: "The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chs. 330 and 333, as amended, as well as Federal regulations, as amended, including 14 CFR Parts 77, 150 and 151 and FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced, and 150/5200-33B, as amended, renumbered or replaced..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 62: Fla. Stat. ch. 330

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source) (embedded in quoted LDC s. 34-1102).

Authority type: statute; as written: F.S. Chs. 330; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 330 (Regulation of Aircraft, Pilots, and Airports) exists and is named in LDC s. 34-1102.

Excerpt read: "Chapter 330 REGULATION OF AIRCRAFT, PILOTS, AND AIRPORTS ... 330.35 Airport zoning protection."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0330/0330ContentsIndex.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 63: Fla. Stat. ch. 333

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source) (embedded in quoted LDC s. 34-1102).

Authority type: statute; as written: F.S. Chs. ... 333; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 333 (Airport Zoning) exists and is named in LDC s. 34-1102.

Excerpt read: "Chapter 333 AIRPORT ZONING"

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.01.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 64: 14 C.F.R. Part 77

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source) (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts 77; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 77 is "Safe, Efficient Use, and Preservation of the Navigable Airspace"; its precision approach surface is 50:1 for 10,000 feet then 40:1 for 40,000 feet, as AC 150/5190-4B's glossary summarizes.

Excerpt read: eCFR: "Part 77—Safe, Efficient Use, and Preservation of the Navigable Airspace"; AC 150/5190-4B glossary: "50:1/40:1 – For all precision instrument runways extending from the primary surface for a distance of 10,000 feet..."

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-E/part-77
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 65: 14 C.F.R. Part 150

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source) (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts ... 150; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 150 is "Airport Noise Compatibility Planning."

Excerpt read: "Part 150—Airport Noise Compatibility Planning"

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-I/part-150

### Second check: not required


## 66: 14 C.F.R. Part 151

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source) (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts ... 151; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 151 is "Federal Aid to Airports."

Excerpt read: "Part 151—Federal Aid to Airports"

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-I/part-151

### Second check: not required


## 67: FAA Advisory Circular 150/5300-13A, Airport Design

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source) (embedded in quoted LDC s. 34-1102).

Authority type: other; as written: FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

AC 150/5300-13A, Airport Design (Sept. 28, 2012) exists and is now cancelled (replaced by 150/5300-13B); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Cancelled list: "150/5300-13A ... Airport Design ... 2012-09-28"; current list: "150/5300-13B ... Airport Design - Change 1"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

### Second check: UNABLE_TO_VERIFY

The first reviewer read the FAA current/cancelled index and related code incorporation, but expressly did not read this circular's primary text. Identity evidence does not meet this audit's primary-text requirement for a verified citation. Original first-check explanation: AC 150/5300-13A, Airport Design (Sept. 28, 2012) exists and is now cancelled (replaced by 150/5300-13B); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: Cancelled list: "150/5300-13A ... Airport Design ... 2012-09-28"; current list: "150/5300-13B ... Airport Design - Change 1"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 68: FAA Advisory Circular 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #8 (source) (embedded in quoted LDC s. 34-1102).

Authority type: other; as written: 150/5200-33B, as amended, renumbered or replaced; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

AC 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports (Aug. 28, 2007) exists and is now cancelled (replaced by 150/5200-33C); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Cancelled list: "150/5200-33B ... Hazardous Wildlife Attractants On or Near Airports ... 2007-08-28"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

### Second check: UNABLE_TO_VERIFY

The first reviewer read the FAA current/cancelled index and related code incorporation, but expressly did not read this circular's primary text. Identity evidence does not meet this audit's primary-text requirement for a verified citation. Original first-check explanation: AC 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports (Aug. 28, 2007) exists and is now cancelled (replaced by 150/5200-33C); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: Cancelled list: "150/5200-33B ... Hazardous Wildlife Attractants On or Near Airports ... 2007-08-28"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 69: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #9 states_in_the_second_assignment_that_the_circuit_court_erred_i_2 (source).

Authority type: other; as written: Fed. Aviation Admin., Advisory Circular No. 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022) at page 2; pincite: 2.

Cited for: Advisory circulars are not binding law (criterion refers to them as 'Federal Aviation Authority Advisory Circulars')

Quotes: ['This AC does not constitute a regulation, and is not legally binding in its own right… Conformity with this AC is voluntary, and nonconformity will not affect rights and obligations under existing statutes and regulations']

Context: 

Fictional by design: False; 

### First check: VERIFIED

AC 150/5190-4B (Sept. 16, 2022) at page 2 contains the quoted non-binding statement.

Excerpt read: "This AC does not constitute a regulation, and is not legally binding in its own right. ... Conformity with this AC is voluntary, and nonconformity will not affect rights and obligations under existing statutes and regulations, except for the projects described in subparagraphs..."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 70: Broward County v. G.B.V. International, Ltd.

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #10 states_in_the_second_assignment_that_the_circuit_court_erred_b_5 (source).

Authority type: case; as written: Broward County v. G.B.V. Int'l, Ltd., 787 So. 2d 838, 845 (Fla. 2001); pincite: 845.

Cited for: Circuit court may only quash, not reverse, a quasi-judicial land use decision

Quotes: ['When a circuit court grants certiorari relief, it quashes the order and leaves the matter pending before the lower tribunal as if no order had been entered.']

Context: 

Fictional by design: False; 

### First check: MISQUOTED

The quoted sentence "When a circuit court grants certiorari relief, it quashes the order and leaves the matter pending before the lower tribunal as if no order had been entered" does not appear in G.B.V. (phrase searches for "as if no order had been entered" and "quashes the order" returned no match). The proposition is supported at *844, where G.B.V. block-quotes Tamiami Trail Tours, but in different words and not at 845.

Excerpt read: *844 (quoting Tamiami Trail Tours, 174 So. 451, 454): "When the order is quashed ... it leaves the subject matter, that is, the controversy pending before the tribunal, commission, or administrative authority, as if no order or judgment had been entered..."

- https://www.courtlistener.com/opinion/1882290/broward-county-v-gbv-intern-ltd/

### Second check: MISQUOTED

The purported G.B.V. quotation is a paraphrase of the court's quoted Tamiami Trail Tours rule, not judicial text from page 845. Actual support is at page 844; the rule that certiorari quashes without substituting a merits decision is sound.

Excerpt read: At page 844 G.B.V. quotes Tamiami on effect of quashing; the rubric's sentence is absent.

- https://app.midpage.ai/document/broward-county-v-gbv-intern-1882290

Model: gpt-6-sol; reasoning effort: high.

## 71: Fla. Const. art. II, s. 3 (cited as art. III, s. 3)

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #11 states_in_the_second_assignment_that_the_circuit_court_s_erred_b (criterion).

Authority type: other; as written: Fla. Const. art. III, § 3; pincite: art. III, § 3.

Cited for: Separation of powers: court substituted its judgment for the Board's legislative function

Quotes: []

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

Article III, section 3 of the Florida Constitution governs sessions of the legislature. The quoted separation-of-powers text is Article II, section 3 ("Branches of government"); the rubric's own URL anchor (A2S03) points to Article II. Real provision, wrong article number.

Excerpt read: Art. II s.3: "The powers of the state government shall be divided into legislative, executive and judicial branches. No person belonging to one branch shall exercise any powers appertaining to either of the other branches unless expressly provided herein." Art. III s.3: "Sessions of the legislature.—(a) ORGANIZATION SESSIONS..."

- https://www.flsenate.gov/Laws/Constitution

### Second check: WRONG_CITATION_REAL_CASE

Florida Constitution article II, section 3 contains the quoted separation-of-powers clause. Article III, section 3 concerns legislative sessions. The criterion also inaccurately calls this site-specific rezoning a legislative function; Snyder classifies that kind of rezoning as quasi-judicial.

Excerpt read: Article II section 3 says no branch may exercise another's powers; article III section 3 covers sessions; Snyder addresses quasi-judicial rezoning.

- https://www.flsenate.gov/Laws/Constitution
- https://syfert.com/florida/cases/627-so-2d-469/bd-of-cty-comrs-of-brevard-v-snyder

Model: gpt-6-sol; reasoning effort: high.

## 72: Fla. Const. art. II, s. 3 (cited as art. III, s. 3)

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #11 (source).

Authority type: other; as written: Fla. Const. art. III, § 3; pincite: art. III, § 3.

Cited for: Separation of powers text

Quotes: ['The powers of the state government shall be divided into legislative, executive and judicial branches. No person belonging to one branch shall exercise any powers appertaining to either of the other branches unless expressly provided herein']

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

Article III, section 3 of the Florida Constitution governs sessions of the legislature. The quoted separation-of-powers text is Article II, section 3 ("Branches of government"); the rubric's own URL anchor (A2S03) points to Article II. Real provision, wrong article number.

Excerpt read: Art. II s.3: "The powers of the state government shall be divided into legislative, executive and judicial branches. No person belonging to one branch shall exercise any powers appertaining to either of the other branches unless expressly provided herein." Art. III s.3: "Sessions of the legislature.—(a) ORGANIZATION SESSIONS..."

- https://www.flsenate.gov/Laws/Constitution

### Second check: WRONG_CITATION_REAL_CASE

The quoted separation-of-powers language is article II, section 3, not article III, section 3, which regulates sessions of the legislature.

Excerpt read: Florida Constitution article II section 3 is headed Branches of Government; article III section 3 is headed Sessions of the Legislature.

- https://www.flsenate.gov/Laws/Constitution

Model: gpt-6-sol; reasoning effort: high.

## 73: Modlin v. City of Miami Beach

Document: assignment-2 rubric.json; location: assignment-2 rubric criterion #11 (source).

Authority type: case; as written: Modlin v. City of Miami Beach, 201 So.2d 70 (Fla. 1967); pincite: .

Cited for: Distinction between legislative and executive/judicial action

Quotes: ['The distinction between legislative action, on the one hand, and executive and judicial action, on the other, is not difficult to define.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted passage appears at 201 So. 2d at 73 (no pin given). Modlin is a tort-immunity case; the passage distinguishes legislative from executive and judicial action as described.

Excerpt read: *73: "The distinction between legislative action, on the one hand, and executive and judicial action, on the other, is not difficult to define. It is sufficient for present purposes to say that the former is typically prospective and nondiscriminatory, whereas the latter operate retroactively and discriminatorily..."

- https://www.courtlistener.com/opinion/1616617/modlin-v-city-of-miami-beach/

### Second check: not required


## 74: Fla. Const. art. V, s. 5(b)

Document: 1774361815-orderpdf.docx; location: Order page image 1, para. 1.

Authority type: other; as written: Article V, Section 5(b) of the Florida Constitution; pincite: 5(b).

Cited for: Basis of the circuit court's first-tier certiorari jurisdiction

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Art. V, s. 5(b) gives circuit courts power to issue writs of certiorari and direct review of administrative action as prescribed by general law.

Excerpt read: "(b) JURISDICTION.—The circuit courts shall have original jurisdiction not vested in the county courts ... They shall have the power to issue writs of mandamus, quo warranto, certiorari, prohibition and habeas corpus..."

- https://www.flsenate.gov/Laws/Constitution

### Second check: not required


## 75: Fla. R. App. P. 9.030(c)(2)

Document: 1774361815-orderpdf.docx; location: Order page image 1, para. 1.

Authority type: court_rule; as written: Fla. R. App. P. 9.030(c)2; pincite: 9.030(c)2.

Cited for: Basis of first-tier certiorari jurisdiction

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Rule 9.030(c)(2) covers circuit-court certiorari review of nonfinal orders; common-law certiorari review of quasi-judicial local action falls under 9.030(c)(3) (original jurisdiction), which the Petition cites. Rule 9.100(f)(1) refers to circuit-court jurisdiction under both (c)(2) and (c)(3), so the cite is imprecise rather than wrong. Read on rules.floridaappellate.com (current text; subdivision not shown as amended for this point).

Excerpt read: 9.030(c)(2): "The certiorari jurisdiction of circuit courts may be sought to review nonfinal orders of lower tribunals other than as prescribed by rule 9.130." (c)(3): "Circuit courts may issue writs of mandamus, prohibition, quo warranto, common law certiorari..."

- https://rules.floridaappellate.com/rule-9-030/
- https://rules.floridaappellate.com/rule-9-100/

### Second check: not required


## 76: Fla. R. App. P. 9.100(c)(2)

Document: 1774361815-orderpdf.docx; location: Order page image 1, para. 1.

Authority type: court_rule; as written: 9.100(c)(2); pincite: 9.100(c)(2).

Cited for: Petition timely filed

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.100(c)(2): petition to review quasi-judicial action of local government due within 30 days of rendition.

Excerpt read: "(2) a petition to review quasi-judicial action of agencies, boards, and commissions of local government, which action is not directly appealable under any other provision of general law but may be subject to review by certiorari"

- https://rules.floridaappellate.com/rule-9-100/

### Second check: not required


## 77: Jennings v. Dade County

Document: 1774361815-orderpdf.docx; location: Order page image 3, para. 2.

Authority type: case; as written: Jennings v Dade County 589 So. 2d 1337 (Fla. 3rd DCA 1991); pincite: .

Cited for: BOCC motion improper because based on facts beyond the quasi-judicial record

Quotes: []

Context: The BOCC motion ... was improper because it was based on facts beyond the quasi-judicial record created in the quasi-judicial on this rezoning. Jennings v Dade County 589 So. 2d 1337 (Fla. 3rd DCA 1991).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Jennings holds that proof of an ex parte communication to quasi-judicial officers raises a presumption of prejudice; it states parties must be informed of all facts on which the commission acts. It loosely supports a rule against deciding on matters outside the record but does not involve a commissioner's motion referring to prior board direction.

Excerpt read: *1340-41: "In quasi-judicial zoning proceedings, the parties must be able to present evidence, cross-examine witnesses, and be informed of all the facts upon which the commission acts." *1339: "We hold that upon proof that a quasi-judicial officer received an ex parte contact, a presumption arises ... that the contact was prejudicial."

- https://www.courtlistener.com/opinion/1837291/jennings-v-dade-county/

### Second check: not required


## 78: Jennings v. Dade County

Document: 1774361815-orderpdf.docx; location: Order page image 3, para. 2.

Authority type: case; as written: Jennings; pincite: .

Cited for: Motion and vote after public comment, as the 'ultimate decision' was made, contradicts Jennings

Quotes: []

Context: The Commission's motion and vote came after public comment and only as the "ultimate decision" was being made in direct contradiction to Jennings.

Fictional by design: False; 

### First check: MISCHARACTERIZED

Jennings addresses prejudicial ex parte information in a quasi-judicial zoning proceeding. Its opinion does not prescribe when a motion may be made after public comment or directly contradict the Order's concern that a new rationale surfaced at the vote.

Excerpt read: Jennings creates a rebuttable prejudice presumption for ex parte contacts and discusses opportunity to answer unknown facts.

- https://app.midpage.ai/document/jennings-v-dade-county-1837291

### Second check: pending


## 79: Fla. Att'y Gen. Op. 94-71 (1994)

Document: 1774361815-orderpdf.docx; location: Order page image 3, para. 2.

Authority type: other; as written: AGO 94-71; pincite: .

Cited for: See also (ex parte / record-based quasi-judicial decision)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

AGO 94-71 (Aug. 18, 1994, to the Brevard County Commission) addresses ex parte communications in quasi-judicial rezonings, including county-owned property and contacts with staff, which should be disclosed on the record. Consistent with the Order's "see also" use.

Excerpt read: "Proof of an ex parte communication creates a rebuttable presumption that a decision is prejudiced... contact with the staff outside the quasi-judicial proceeding could result in an allegation of ex parte communication. Such communication, therefore, should be disclosed to all interested parties and placed on the record..."

- https://www.myfloridalegal.com/ag-opinions/proof-of-ex-parte-communications-by-cty-commissioners
- https://www.courtlistener.com/opinion/3386708/ago/

### Second check: not required


## 80: Jennings v. Dade County

Document: 1774361815-orderpdf.docx; location: Order page image 3, para. 3.

Authority type: case; as written: Jennings v Dade County 589 So. 2d 1337 (Fla. 3rd DCA 1991); pincite: .

Cited for: Basing the motion and vote on information outside the hearing violated procedural due process

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Jennings holds that proof of an ex parte communication to quasi-judicial officers raises a presumption of prejudice; it states parties must be informed of all facts on which the commission acts. It loosely supports a rule against deciding on matters outside the record but does not involve a commissioner's motion referring to prior board direction.

Excerpt read: *1340-41: "In quasi-judicial zoning proceedings, the parties must be able to present evidence, cross-examine witnesses, and be informed of all the facts upon which the commission acts." *1339: "We hold that upon proof that a quasi-judicial officer received an ex parte contact, a presumption arises ... that the contact was prejudicial."

- https://www.courtlistener.com/opinion/1837291/jennings-v-dade-county/

### Second check: not required


## 81: Jennings v. Dade County

Document: 1774361815-orderpdf.docx; location: Order page image 5, para. 1.

Authority type: case; as written: Jennings; pincite: .

Cited for: Predetermination and 'four years of board direction' exceeded the bounds of the quasi-judicial hearing

Quotes: []

Context: ...the ultimate decision that was based on "four years of board direction" exceeding the bounds of the quasi-judicial hearing violation of Jennings.

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Jennings holds that proof of an ex parte communication to quasi-judicial officers raises a presumption of prejudice; it states parties must be informed of all facts on which the commission acts. It loosely supports a rule against deciding on matters outside the record but does not involve a commissioner's motion referring to prior board direction.

Excerpt read: *1340-41: "In quasi-judicial zoning proceedings, the parties must be able to present evidence, cross-examine witnesses, and be informed of all the facts upon which the commission acts." *1339: "We hold that upon proof that a quasi-judicial officer received an ex parte contact, a presumption arises ... that the contact was prejudicial."

- https://www.courtlistener.com/opinion/1837291/jennings-v-dade-county/

### Second check: not required


## 82: Lee County LDC s. 34-1102

Document: 1774361815-orderpdf.docx; location: Order page image 5, para. 2.

Authority type: regulation; as written: LDC Division 12 -AIRPORT COMPATABILITY DISTRICT LDC 34 -1102; pincite: .

Cited for: County's application did not comply with the Airport Compatibility District provisions adopting FAA guidance by reference

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The Order relies on LDC s. 34-1102 as adopting FAA land use compatibility and wildlife hazard advisories and their updates. The section names AC 150/5200-33B "as amended, renumbered or replaced" (now 150/5200-33C), giving textual support for the wildlife AC, but it is a purpose statement, does not name AC 150/5190-4B, and both ACs state they are not legally binding in their own right.

Excerpt read: LDC 34-1102: "...FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced, and 150/5200-33B, as amended, renumbered or replaced..."; AC 150/5200-33C p.i: "This AC does not constitute a regulation, is not mandatory, and is not legally binding in its own right."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150-5200-33C.pdf

### Second check: not required


## 83: Lee County LDC s. 34-1102

Document: 1774361815-orderpdf.docx; location: Order page image 5-6, para. 2.

Authority type: regulation; as written: LDC Division 12 -AIRPORT COMPATABILITY DISTRICT LDC 34 -1102; pincite: .

Cited for: Same (second citation in the sentence)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The Order relies on LDC s. 34-1102 as adopting FAA land use compatibility and wildlife hazard advisories and their updates. The section names AC 150/5200-33B "as amended, renumbered or replaced" (now 150/5200-33C), giving textual support for the wildlife AC, but it is a purpose statement, does not name AC 150/5190-4B, and both ACs state they are not legally binding in their own right.

Excerpt read: LDC 34-1102: "...FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced, and 150/5200-33B, as amended, renumbered or replaced..."; AC 150/5200-33C p.i: "This AC does not constitute a regulation, is not mandatory, and is not legally binding in its own right."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150-5200-33C.pdf

### Second check: not required


## 84: Fla. Stat. s. 333.04(2)

Document: 1774361815-orderpdf.docx; location: Order page image 6, para. 1.

Authority type: statute; as written: FS 333.04(2) (Petition p 45); pincite: 333.04(2).

Cited for: Most stringent requirement prevails

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Section 333.04(2) quoted accurately (2024): in a conflict the more stringent limitation or requirement governs.

Excerpt read: "(2) CONFLICT.—In the event of conflict between any airport zoning regulations adopted under this chapter and any other regulations applicable to the same area ... the more stringent limitation or requirement shall govern and prevail."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.04.html

### Second check: not required


## 85: FAA airport compatibility and wildlife hazard advisory circulars (AC 150/5190-4B; AC 150/5200-33C)

Document: 1774361815-orderpdf.docx; location: Order page image 6, para. 1.

Authority type: other; as written: Airport Compatibility, Wildlife Hazard FAA Advisories (Petition 37-59); pincite: .

Cited for: Most recent FAA advisories on wastewater plant siting, adopted by reference in the LDC, should have been applied

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The Order's "Airport Compatibility, Wildlife Hazard FAA Advisories" corresponds to AC 150/5190-4B and AC 150/5200-33C as cited in the Petition (pp. 37-59). AC 150/5200-33C is the replacement of AC 150/5200-33B named in LDC s. 34-1102, but neither AC is a regulation: each states it is not legally binding in its own right, and LDC s. 34-1102 does not name AC 150/5190-4B.

Excerpt read: AC 150/5190-4B p.2: "This AC does not constitute a regulation, and is not legally binding in its own right."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150-5200-33C.pdf
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 86: Lee County LDC s. 34-5(c) (unattributed quotation)

Document: 1774361815-orderpdf.docx; location: Order page image 6, para. 1.

Authority type: regulation; as written: [quoted without attribution following LDC 34-1102 and FS 333.04(2)]; pincite: .

Cited for: Most restrictive regulation applies

Quotes: ['Whenever the regulations and requirements of this chapter are at variance with the requirements of any other lawfully enacted and adopted rules, regulations, ordinance or laws, the most restrictive will apply.']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The quoted "at variance ... most restrictive will apply" sentence is LDC s. 34-5(c) (Interpretation and regulatory intent), not s. 34-1102 or F.S. 333.04(2), which the Order cites in the same sentence without naming s. 34-5. The quote is otherwise verbatim ("ordinance" vs "ordinances").

Excerpt read: s.34-5(c): "Whenever the regulations and requirements of this chapter are at variance with the requirements of any other lawfully enacted and adopted rules, regulations, ordinances or laws, the most restrictive will apply."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 87: Lee County Resolution No. Z-23-022 (as captioned)

Document: 1774361815-orderpdf.docx; location: Order page image 1, caption.

Authority type: other; as written: Rezoning Resolution Z-23-022; pincite: .

Cited for: Identifies the rezoning under review

Quotes: []

Context: 

Fictional by design: False; 

### First check: CITATION_POINTS_TO_DIFFERENT_CASE

The Order caption says Z-23-022, but Lee County's official September 2023 zoning agenda assigns Z-23-022 to Daniels Parkway South, DCI2022-00002. The supplied January 2024 wastewater resolution is Z-23-035, DCI2023-00011. This is a wrong project identifier in the scenario record, not fabricated legal authority.

Excerpt read: Agenda cover pairs DCI2022-00002 with Z-23-022 and Daniels Parkway South; supplied resolution cover identifies Z-23-035.

- https://results.leegov.com/Home/DownloadFile/KT0000315224

### Second check: pending


## 88: Fla. R. App. P. 9.100(f)(2)

Document: 1774361815-petition.docx; location: petition.docx.md line 19 (caption).

Authority type: court_rule; as written: F.R.A.P. 9.100(f)(2); pincite: 9.100(f)(2).

Cited for: Caption statement that petition is filed under subdivision (f)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.100(f)(2) requires a circuit-court review petition's caption to state that it is filed pursuant to subdivision (f); the Petition's caption statement complies.

Excerpt read: "(f) Review Proceedings in Circuit Court... (2) Caption. The caption shall contain a statement that the petition is filed pursuant to this subdivision."

- https://rules.floridaappellate.com/rule-9-100/

### Second check: not required


## 89: Lee County Resolution No. Z-23-022 (as captioned)

Document: 1774361815-petition.docx; location: petition.docx.md line 27 (caption).

Authority type: other; as written: Rezoning Resolution Z-23-022; pincite: .

Cited for: Identifies the rezoning under review

Quotes: []

Context: 

Fictional by design: False; 

### First check: CITATION_POINTS_TO_DIFFERENT_CASE

The Petition caption repeats Z-23-022, an actual identifier for Daniels Parkway South on Lee County's agenda; the Petition's body and attached wastewater resolution identify the litigated action as Z-23-035. This is a record caption defect, not fabricated law.

Excerpt read: County agenda assigns Z-23-022 to DCI2022-00002; attached resolution assigns wastewater DCI2023-00011 to Z-23-035.

- https://results.leegov.com/Home/DownloadFile/KT0000315224

### Second check: pending


## 90: Fla. Const. art. V, s. 5(b)

Document: 1774361815-petition.docx; location: petition.docx.md line 53-55 (JURISDICTION).

Authority type: other; as written: Article V, Section 5(b) Florida Constitution; pincite: 5(b).

Cited for: Circuit court jurisdiction to issue writs of certiorari

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Art. V, s. 5(b) gives circuit courts power to issue writs of certiorari and direct review of administrative action as prescribed by general law.

Excerpt read: "(b) JURISDICTION.—The circuit courts shall have original jurisdiction not vested in the county courts ... They shall have the power to issue writs of mandamus, quo warranto, certiorari, prohibition and habeas corpus..."

- https://www.flsenate.gov/Laws/Constitution

### Second check: not required


## 91: Fla. R. App. P. 9.030(c)(3)

Document: 1774361815-petition.docx; location: petition.docx.md line 55-57 (JURISDICTION).

Authority type: court_rule; as written: Florida Rule Appellate Procedure 9.030(c)(3); pincite: 9.030(c)(3).

Cited for: Circuit court jurisdiction

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.030(c)(3) gives circuit courts original jurisdiction to issue writs of common law certiorari.

Excerpt read: "(3) Original Jurisdiction. Circuit courts may issue writs of mandamus, prohibition, quo warranto, common law certiorari, and habeas corpus..."

- https://rules.floridaappellate.com/rule-9-030/

### Second check: not required


## 92: Fla. R. App. P. 9.100(b)

Document: 1774361815-petition.docx; location: petition.docx.md line 59 (JURISDICTION).

Authority type: court_rule; as written: Florida Rules of Appellate Procedure 9.100(b); pincite: 9.100(b).

Cited for: Petition filed pursuant to

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.100(b) governs commencement of original proceedings by petition and the parties.

Excerpt read: "(b) Commencement; Parties. The original jurisdiction of the court shall be invoked by filing a petition..."

- https://rules.floridaappellate.com/rule-9-100/

### Second check: not required


## 93: Fla. R. App. P. 9.100(c)

Document: 1774361815-petition.docx; location: petition.docx.md line 59 (JURISDICTION).

Authority type: court_rule; as written: 9.100(c); pincite: 9.100(c).

Cited for: Petition filed pursuant to (timing)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.100(c) sets a 30-day deadline for petitions for certiorari and petitions to review quasi-judicial action of local government; quoted text matches. Exclusivity of certiorari review of quasi-judicial action is supported by Dickerson and Lee County LDC s. 34-85(a), not by the rule itself.

Excerpt read: "(c) Petitions for Certiorari; Review of NonFinal Agency Action... The following shall be filed within 30 days of rendition of the order to be reviewed: (1) a petition for certiorari; (2) a petition to review quasi-judicial action of agencies, boards, and commissions of local government..."

- https://rules.floridaappellate.com/rule-9-100/
- https://www.courtlistener.com/opinion/1767817/city-of-fort-pierce-v-dickerson/

### Second check: not required


## 94: Fla. R. App. P. 9.190(b)(3)

Document: 1774361815-petition.docx; location: petition.docx.md line 59 (JURISDICTION).

Authority type: court_rule; as written: 9.190(b)(3); pincite: 9.190(b)(3).

Cited for: Review of quasi-judicial decisions by certiorari

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.190(b)(3): review of quasi-judicial decisions of bodies not subject to the APA is commenced by petition for certiorari under rules 9.100(b) and (c).

Excerpt read: "(3) Review of quasi-judicial decisions of any administrative body, agency, board, or commission not subject to the Administrative Procedure Act shall be commenced by filing a petition for certiorari in accordance with rules 9.100(b) and (c)..."

- https://rules.floridaappellate.com/rule-9-190/

### Second check: not required


## 95: Broward County v. G.B.V. International, Ltd.

Document: 1774361815-petition.docx; location: petition.docx.md line 63-67 (STANDARD OF REVIEW).

Authority type: case; as written: Broward County v. G.B.V. International, Ltd., 787 So.2d 838 at 843 (Fla.2001); pincite: 843.

Cited for: Three-part first-tier certiorari standard

Quotes: ["In first tier certiorari proceedings, the circuit court must determine: '(1) whether procedural due process is accorded, (2) whether the essential requirements of the law have been observed, and (3) whether the administrative findings and judgment are supported by competent substantial evidence."]

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

G.B.V. at 843 quotes Vaillant's three-part first-tier standard (with bracketed numbers [1]-[3]); the Petition's lead-in "In first tier certiorari proceedings, the circuit court must determine" is not G.B.V.'s wording, and the Petition uses (1)-(3). Substance and pin cite correct.

Excerpt read: *843: "Where a party is entitled as a matter of right to seek review in the circuit court from administrative action, the circuit court must determine [1] whether procedural due process is accorded, [2] whether the essential requirements of the law have been observed, and [3] whether the administrative findings and judgment are supported by competent substantial evidence."

- https://www.courtlistener.com/opinion/1882290/broward-county-v-gbv-intern-ltd/

### Second check: not required


## 96: City of Deerfield Beach v. Vaillant

Document: 1774361815-petition.docx; location: petition.docx.md line 69-71 (STANDARD OF REVIEW).

Authority type: case; as written: Deerfield Beach v. Valliant, 419 So. 2d 624 at 626 (Fla. 1982); pincite: 626.

Cited for: Source of the three-part standard quoted in G.B.V.

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

City of Deerfield Beach v. Vaillant, 419 So. 2d 624, 626 (Fla. 1982) states the first-tier standard. The Petition misspells the name ("Valliant").

Excerpt read: "...the circuit court must determine whether procedural due process is accorded, whether the essential requirements of the law have been observed, and whether the administrative findings and judgment are supported by competent substantial evidence."

- https://www.courtlistener.com/opinion/1914497/city-of-deerfield-beach-v-vaillant/

### Second check: not required


## 97: Renard v. Dade County

Document: 1774361815-petition.docx; location: petition.docx.md line 79 (THE PETITIONERS).

Authority type: case; as written: Renard v. Dade County, 261 So. 2d 832 (Fla. 1972); pincite: .

Cited for: Test for standing in rezoning cases; proximity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Renard sets the standing tests for zoning challenges; proximity is a factor (261 So. 2d at 837-38).

Excerpt read: Quoted in Rinker, 528 So. 2d at 906: a court is to consider "the proximity of [its] property to the area to be zoned or rezoned, the character of the neighborhood, ... and the type of change proposed." Renard, 261 So. 2d at 837.

- https://www.courtlistener.com/opinion/1764932/renard-v-dade-county/

### Second check: not required


## 98: Rinker Materials Corp. v. Metropolitan Dade County

Document: 1774361815-petition.docx; location: petition.docx.md line 79-83 (THE PETITIONERS).

Authority type: case; as written: Rinker Materials Corp. v. Metropolitan Dade County 528 So.2d 904, 906-907 (Fla. 3rd DCA., 1987); pincite: 906-907.

Cited for: Standing considers proximity and the type and scale of the project

Quotes: ["should not only consider the proximity of the property, but the type and scale of the challenged project in relation to Petitioner's property."]

Context: 

Fictional by design: False; 

### First check: MISQUOTED

The quoted language ("should not only consider the proximity of the property, but the type and scale of the challenged project in relation to Petitioner's property") does not appear in Rinker; searches for "type and scale", "scale" and "should not only" found nothing. At 906-07 Rinker quotes Renard's factors (proximity, character of the neighborhood, type of change proposed). Citation details (528 So. 2d 904, 3d DCA 1987) correct.

Excerpt read: *906: "a court is to consider 'the proximity of [its] property to the area to be zoned or rezoned, the character of the neighborhood, ... and the type of change proposed.'"

- https://www.courtlistener.com/opinion/1793709/rinker-materials-corp-v-metropolitan-dade-county/

### Second check: MISQUOTED

Rinker's standing analysis quotes Renard's proximity, neighborhood character, and type-of-change factors. The Petition's asserted verbatim 'type and scale' sentence does not appear in the judicial opinion, although project nature is relevant in substance.

Excerpt read: The opinion identifies proximity, neighborhood character, and type of proposed change, without the Petition's wording.

- https://openjurist.org/528/so2d/904/rinker-materials-corp-v-metropolitan-dade-county-1793709

Model: gpt-6-sol; reasoning effort: high.

## 99: City of St. Petersburg, Bd. of Adjustment v. Marelli

Document: 1774361815-petition.docx; location: petition.docx.md line 83 (THE PETITIONERS).

Authority type: case; as written: City of St. Petersburg, Bd. of Adjustment v. Marelli 728 So.2d 1197, 1198 (Fla 2nd DCA, 1999); pincite: 1198.

Cited for: See also: neighbors' standing

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

City of St. Petersburg, Bd. of Adjustment v. Marelli, 728 So. 2d 1197, 1198 (Fla. 2d DCA 1999) recognizes that neighboring owners affected by zoning changes have standing.

Excerpt read: "A multitude of cases recognize that neighboring property owners affected by zoning changes have standing to challenge the changes."

- https://www.courtlistener.com/opinion/1666072/city-of-st-petersburg-v-marelli/

### Second check: not required


## 100: Renard v. Dade County

Document: 1774361815-petition.docx; location: petition.docx.md line 83 (THE PETITIONERS).

Authority type: case; as written: Renard v. Dade County, 261 So.2d 832 (Fla. 1972); pincite: .

Cited for: Nearby owners affected more than the public have standing

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Renard sets the standing tests for zoning challenges; proximity is a factor (261 So. 2d at 837-38).

Excerpt read: Quoted in Rinker, 528 So. 2d at 906: a court is to consider "the proximity of [its] property to the area to be zoned or rezoned, the character of the neighborhood, ... and the type of change proposed." Renard, 261 So. 2d at 837.

- https://www.courtlistener.com/opinion/1764932/renard-v-dade-county/

### Second check: not required


## 101: Upper Keys Citizens Association, Inc. v. Wedel

Document: 1774361815-petition.docx; location: petition.docx.md line 83 (THE PETITIONERS).

Authority type: case; as written: Upper Keys Citizens Coalition v. Wedel, 341 So.2d 1062 (3rd DCA 1987); pincite: .

Cited for: Standing of affected neighbors

Quotes: []

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

The case at 341 So. 2d 1062 is Upper Keys Citizens Association, Inc. v. Wedel (Fla. 3d DCA 1977), not "Upper Keys Citizens Coalition" and not 1987. It holds that a citizens' association need not allege special injury to challenge a zoning action as illegally enacted.

Excerpt read: "UPPER KEYS CITIZENS ASSOCIATION, INC. ... v. Martha WEDEL ... District Court of Appeal of Florida, Third District. February 1, 1977."

- https://www.courtlistener.com/opinion/1814581/upper-keys-citizens-assn-inc-v-wedel/

### Second check: WRONG_CITATION_REAL_CASE

The decision at 341 So. 2d 1062 is Upper Keys Citizens Association, Inc. v. Wedel, decided in 1977, not a 1987 Upper Keys Citizens Coalition decision. The association standing discussion is real.

Excerpt read: Opinion header identifies Upper Keys Citizens Association v. Wedel, Third DCA 1977.

- https://case-law.vlex.com/vid/upper-keys-citizens-ass-892835762

Model: gpt-6-sol; reasoning effort: high.

## 102: Save Brickell Ave., Inc. v. City of Miami

Document: 1774361815-petition.docx; location: petition.docx.md line 83 (THE PETITIONERS).

Authority type: case; as written: Save Brickell Ave., Inc. v City of Miami, 393 So.2d 1197 (3rd DCA 1981); pincite: .

Cited for: Standing of affected neighbors

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Save Brickell Ave., Inc. v. City of Miami, 393 So. 2d 1197 (Fla. 3d DCA 1981) holds an affected citizen organization has standing to challenge a zoning resolution as void for lack of notice.

Excerpt read: "Save Brickell Avenue is an 'affected ... citizen' which has standing to attack the enactment in question on the ground ... that it is void or invalid because the 'required notice was not given.'"

- https://www.courtlistener.com/opinion/1798835/save-brickell-ave-inc-v-city-of-miami/

### Second check: not required


## 103: Board of County Commissioners of Brevard County v. Snyder

Document: 1774361815-petition.docx; location: petition.docx.md line 199 (VIOLATIONS OF DUE PROCESS).

Authority type: case; as written: Board of County Com'rs of Brevard County v. Snyder, 627 So.2d 469 (Fla. 1993); pincite: .

Cited for: Snyder's discussion of political influence in zoning

Quotes: ['Richard Babcock deplored the effect of …rank political influence on the local decision-making process.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted passage appears in Snyder, 627 So. 2d at 472-73 (the Petition elides "neighborhoodism and").

Excerpt read: *472-73: "Richard Babcock deplored the effect of 'neighborhoodism' and rank political influence on the local decision-making process. Richard F. Babcock, The Zoning Game (1966). Mandelker and Tarlock recently stated that 'zoning decisions are too often ad hoc, sloppy and self-serving decisions...'"

- https://www.courtlistener.com/opinion/1910929/bd-of-cty-comrs-of-brevard-v-snyder/

### Second check: not required


## 104: Richard F. Babcock, The Zoning Game (1966)

Document: 1774361815-petition.docx; location: petition.docx.md line 199 (within Snyder quotation).

Authority type: restatement_or_treatise; as written: Richard F. Babcock, The Zoning Game (1966); pincite: .

Cited for: Political influence in local zoning

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Cited only as quoted within Snyder, which reproduces the citation as the Petition gives it (Snyder at 472-73). The book itself was not read.

Excerpt read: Snyder *473: "Richard F. Babcock, The Zoning Game (1966)."

- https://www.courtlistener.com/opinion/1910929/bd-of-cty-comrs-of-brevard-v-snyder/

### Second check: not required


## 105: Mandelker & Tarlock, Shifting the Presumption of Constitutionality in Land-Use Law, 24 Urb. Law. 1 (1992)

Document: 1774361815-petition.docx; location: petition.docx.md line 199 (within Snyder quotation).

Authority type: restatement_or_treatise; as written: Daniel R. Mandelker and A. Dan Tarlock, Shifting the Presumption of Constitutionality in Land-Use Law, 24 Urb.Law. 1, 2 (1992); pincite: 2.

Cited for: Zoning decisions too often ad hoc and self-serving

Quotes: ['zoning decisions are too often ad hoc, sloppy and self-serving decisions with welldefined adverse consequences without off-setting benefits.']

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Cited only as quoted within Snyder, which gives the same citation and quotation (Snyder at 473). The article itself was not read.

Excerpt read: Snyder *473: "Daniel R. Mandelker and A. Dan Tarlock, Shifting the Presumption of Constitutionality in Land-Use Law, 24 Urb.Law. 1, 2 (1992)."

- https://www.courtlistener.com/opinion/1910929/bd-of-cty-comrs-of-brevard-v-snyder/

### Second check: not required


## 106: Allapattah Community Ass'n v. City of Miami

Document: 1774361815-petition.docx; location: petition.docx.md line 199-201 (VIOLATIONS OF DUE PROCESS).

Authority type: case; as written: Allapattah Community Ass'n, Inc. of Florida v. City of Miami, 379 So.2d 387 (Fla. App. 1980); pincite: .

Cited for: Zoning action cannot rest on supporters' power to work their will

Quotes: ['The law, however, will not and cannot approve a zoning regulation or any governmental action adversely affecting the rights of others which is based on no more than the fact that those who support it have the power to work their will.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted sentence appears in Allapattah Community Ass'n v. City of Miami, 379 So. 2d 387, 394 (Fla. 3d DCA 1980) (no pin given; court shown only as "Fla. App.").

Excerpt read: "The law, however, will not and cannot approve a zoning regulation—or any governmental action adversely affecting the rights of others—which is based on no more than the fact that those who support it have the power to work their will."

- https://www.courtlistener.com/opinion/1688124/allapattah-community-association-inc-v-city-of-miami/

### Second check: not required


## 107: Board of County Commissioners of Brevard County v. Snyder

Document: 1774361815-petition.docx; location: petition.docx.md line 263-267 (VIOLATIONS OF DUE PROCESS).

Authority type: case; as written: Brevard County v. Snyder, 627 So.2d 469 (Fla. 1993); pincite: .

Cited for: Two-step burden test for rezoning applications

Quotes: ['1. a landowner seeking to rezone property has the burden of proving that the proposal is consistent with the comprehensive plan and complies with all procedural requirements of the zoning ordinance. 2. At this point, the burden shifts to the governmental board to demonstrate that maintaining the existing zoning classification with respect to the property accomplishes a legitimate public purpose.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Snyder, 627 So. 2d at 476, states the two-step burden allocation as quoted.

Excerpt read: *476: "we hold that a landowner seeking to rezone property has the burden of proving that the proposal is consistent with the comprehensive plan and complies with all procedural requirements of the zoning ordinance. At this point, the burden shifts to the governmental board to demonstrate that maintaining the existing zoning classification with respect to the property accomplishes a legitimate public purpose."

- https://www.courtlistener.com/opinion/1910929/bd-of-cty-comrs-of-brevard-v-snyder/

### Second check: not required


## 108: Fla. Stat. ch. 162

Document: 1774361815-petition.docx; location: petition.docx.md line 307.

Authority type: statute; as written: Florida Statutes Chapter 162; pincite: .

Cited for: Governs adoption of rezoning resolutions; preventing public from speaking to officials violates it

Quotes: []

Context: ...violates constitutional procedural due process not just Florida Statutes Chapter 162 and Chapter 286 governing the adoption of rezoning resolutions and Florida's Sunshine Law

Fictional by design: False; 

### First check: MISCHARACTERIZED

Chapter 162 is "County or Municipal Code Enforcement" (code enforcement boards and supplemental enforcement procedures). It does not govern adoption of rezoning resolutions or public participation, the use the Petition makes of it.

Excerpt read: "Chapter 162 COUNTY OR MUNICIPAL CODE ENFORCEMENT PART I LOCAL GOVERNMENT CODE ENFORCEMENT BOARDS (ss. 162.01-162.13) PART II SUPPLEMENTAL COUNTY OR MUNICIPAL CODE OR ORDINANCE ENFORCEMENT PROCEDURES"

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0100-0199/0162/0162ContentsIndex.html

### Second check: MISCHARACTERIZED

Florida Statutes chapter 162 governs county or municipal code enforcement, including enforcement boards and fines. It is not the statute governing adoption of this rezoning resolution or a general right to speak privately with officials.

Excerpt read: Chapter heading and sections address code-enforcement boards, procedures, violations, and penalties.

- https://www.flsenate.gov/Laws/Statutes/2024/Chapter162/All

Model: gpt-6-sol; reasoning effort: high.

## 109: Fla. Stat. ch. 286

Document: 1774361815-petition.docx; location: petition.docx.md line 307.

Authority type: statute; as written: Chapter 286; pincite: .

Cited for: Governs adoption of rezoning resolutions; Sunshine Law

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Chapter 286 (Public Business: Miscellaneous Provisions) contains the Sunshine Law (s. 286.011) and s. 286.0115 on access to officials in quasi-judicial land use matters. It does not itself govern adoption of rezoning resolutions, so the Petition's description is loose.

Excerpt read: "286.011 Public meetings and records... 286.0115 Access to local public officials; quasi-judicial proceedings on local government land use matters."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0200-0299/0286/0286ContentsIndex.html

### Second check: not required


## 110: Evergreen the Tree Treasurers of Charlotte County, Inc. v. Charlotte County Board of County Commissioners

Document: 1774361815-petition.docx; location: petition.docx.md line 307-309.

Authority type: case; as written: Evergreen the Tree Treasurers v. Charlotte County 810 So. 2d 526 (Fla. 2nd DCA 2002); pincite: .

Cited for: Preventing affected landowners from speaking to their elected officials violates due process and the Sunshine Law

Quotes: []

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

Evergreen (810 So. 2d 526, Fla. 2d DCA 2002) holds that a staff committee exercising delegated quasi-judicial authority is subject to the Sunshine Law and that deciding before taking public input at the meeting denied due process. It does not hold that rules barring private ex parte contact with elected officials violate due process or the Sunshine Law, the proposition the Petition cites it for.

Excerpt read: *532: "Hence, any DRC meeting at which quasi-judicial action will be taken is subject to Florida's Sunshine Law."

- https://www.courtlistener.com/opinion/1604534/evergreen-tree-treas-of-charlotte-county-inc-v-charlotte-cty-bd-of-county-commissioners/

### Second check: MISCHARACTERIZED

Evergreen concerned a delegated development-review committee making a decision at a meeting before hearing public input. It does not hold that a bar on private ex parte contacts with commissioners violates due process or Sunshine law.

Excerpt read: The opinion remands after a committee reached its decision before receiving public comment at the meeting.

- https://law.justia.com/cases/florida/second-district-court-of-appeal/2002/2d00-4804.html

Model: gpt-6-sol; reasoning effort: high.

## 111: Lee County LDC s. 2-191 ("Lee County Code")

Document: 1774361815-petition.docx; location: petition.docx.md line 311.

Authority type: regulation; as written: Lee County Code; pincite: .

Cited for: Prohibits the public from speaking with elected officials as ex parte communications

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 2-191(b)(1) bars communications with a Commissioner about the substance of a pending rezoning. Last amended by Ord. 22-11 (May 17, 2022), so the text is unchanged since before the documents and January 1, 2025.

Excerpt read: "No person may communicate with an individual Commissioner ... regarding the substance (nonprocedural aspects) of a pending rezoning action or appeal..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH2AD_ARTVUNCO_S2-191PRLIUNCO

### Second check: not required


## 112: Fla. Stat. s. 286.0115(1) ("Florida Statutes")

Document: 1774361815-petition.docx; location: petition.docx.md line 311.

Authority type: statute; as written: Florida Statutes; pincite: .

Cited for: Ex parte communications can be disclosed

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Section 286.0115(1)(a) lets a county adopt a disclosure process for ex parte communications with local public officials, supporting the petition's statement that such communications can be disclosed under Florida Statutes.

Excerpt read: "(1)(a) A county or municipality may adopt an ordinance or resolution removing the presumption of prejudice from ex parte communications with local public officials by establishing a process to disclose ex parte communications..."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0200-0299/0286/Sections/0286.0115.html

### Second check: not required


## 113: Town of Palm Beach v. Gradison

Document: 1774361815-petition.docx; location: petition.docx.md line 311 (unattributed quotation).

Authority type: case; as written: [unattributed]; pincite: .

Cited for: When in doubt, follow the open-meeting policy

Quotes: ['When in doubt, the members of any board, agency, authority, or commission should follow the open-meeting policy of the State']

Context: 

Fictional by design: False; 

### First check: VERIFIED

The Petition quotes, without attribution, Gradison's statement at 296 So. 2d at 477.

Excerpt read: *477: "The principle to be followed is very simple: When in doubt, the members of any board, agency, authority or commission should follow the open-meeting policy of the State."

- https://www.courtlistener.com/opinion/1917187/town-of-palm-beach-v-gradison/

### Second check: not required


## 114: Fla. Att'y Gen. Op. (July 15, 1994) (attributed to 'The Florida Supreme Court')

Document: 1774361815-petition.docx; location: petition.docx.md line 313.

Authority type: other; as written: The Florida Supreme Court held that; pincite: .

Cited for: Courts have recognized the importance of public participation in open meetings

Quotes: ['The courts have recognized the importance of public participation in open meetings. The Florida Supreme Court has stated that']

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

The Petition attributes to "The Florida Supreme Court" a quotation that begins "The courts have recognized the importance of public participation in open meetings." That sentence comes from a July 1994 Florida Attorney General opinion (to the Sarasota County Attorney), which in turn quotes Doran; it is not a Florida Supreme Court holding. (The AG opinion's number was not confirmed.)

Excerpt read: AG opinion (July 15, 1994): "The courts have recognized the importance of public participation in open meetings. The Florida Supreme Court has stated that 'specified boards and commissions . . . should not be allowed to deprive the public of this inalienable right to be present and to be heard at all deliberations wherein decisions affecting the public are being made.'"

- https://www.courtlistener.com/opinion/3383177/ago/

### Second check: MISCHARACTERIZED

The Petition's introductory sentence is the Florida Attorney General's prose in a 1994 Sunshine opinion, not a Florida Supreme Court quotation. The following passage from Doran is genuine Supreme Court text. The error is attribution of the combined quotation, not fabrication of the Doran language.

Excerpt read: The AG opinion introduces public-participation importance in its own voice, then expressly quotes the Supreme Court's Doran passage.

- https://www.myfloridalegal.com/ag-opinions/sunshine-law-to-political-forums

Model: gpt-6-sol; reasoning effort: high.

## 115: Board of Public Instruction of Broward County v. Doran

Document: 1774361815-petition.docx; location: petition.docx.md line 313.

Authority type: case; as written: Board of Public Instruction of Broward County v. Doran, 224 So. 2d 693, 699 (Fla. 1969); pincite: 699.

Cited for: Right to be present and heard at public deliberations

Quotes: ['specified boards and commissions . . . should not be allowed to deprive the public of this inalienable right to be present and to be heard at all deliberations wherein decisions affecting the public are being made.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted language appears in Board of Public Instruction of Broward County v. Doran, 224 So. 2d 693, 699 (Fla. 1969).

Excerpt read: *699: "...these specified boards and commissions, through devious ways, should not be allowed to deprive the public of this inalienable right to be present and to be heard at all deliberations wherein decisions affecting the public are being made."

- https://www.courtlistener.com/opinion/1659111/board-of-public-instruction-of-broward-cty-v-doran/

### Second check: not required


## 116: City of Miami Beach v. Berns

Document: 1774361815-petition.docx; location: petition.docx.md line 313.

Authority type: case; as written: City of Miami Beach v. Berns, 245 So. 2d 38, 41 (Fla. 1971); pincite: 41.

Cited for: Evil of closed-door government

Quotes: ['The evil of closed door operation of government without permitting public scrutiny and participation is what the law seeks to prohibit.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted sentence appears in City of Miami Beach v. Berns, 245 So. 2d 38, 41 (Fla. 1971).

Excerpt read: *41: "The evil of closed door operation of government without permitting public scrutiny and participation is what the law seeks to prohibit."

- https://www.courtlistener.com/opinion/1762561/city-of-miami-beach-v-berns/

### Second check: not required


## 117: Town of Palm Beach v. Gradison

Document: 1774361815-petition.docx; location: petition.docx.md line 313.

Authority type: case; as written: Town of Palm Beach v. Gradison, 296 So. 2d 473, 475 (Fla. 1974); pincite: 475.

Cited for: Meetings as a marketplace of ideas

Quotes: ['a meeting as being "a marketplace of ideas, so that the governmental agency may have sufficient input from the citizens who are going to be affected by the subsequent action of the [public agency]."']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted language appears in Town of Palm Beach v. Gradison, 296 So. 2d 473, 475 (Fla. 1974) (the bracketed "[public agency]" replaces "municipality").

Excerpt read: *475: "Every meeting of any board, commission, agency or authority of a municipality should be a marketplace of ideas, so that the governmental agency may have sufficient input from the citizens who are going to be affected by the subsequent action of the municipality."

- https://www.courtlistener.com/opinion/1917187/town-of-palm-beach-v-gradison/

### Second check: not required


## 118: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 389-397.

Authority type: other; as written: Advisory Circular, Subject: Airport Land Use Compatibility, Planning Date: 9/16/2022 ... AC No: 150/5190-4B ... Table 2-2; pincite: 2-15.

Cited for: Airport sponsor owning land expected to prevent new incompatible uses

Quotes: ['If the airport sponsor owns the land ... Because the sponsor has total land use control, the FAA expects that the sponsor will establish all necessary protections to prevent new incompatible land uses.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: Table 2-2: "If the airport sponsor owns the land: Because the sponsor has total land use control, the FAA expects that the sponsor will establish all necessary protections to prevent new incompatible land uses."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 119: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 399.

Authority type: other; as written: FAA Airport Land Use Compatibility Circular; pincite: .

Cited for: Intended for a diverse audience including sponsors, local governments and officials

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: p.2: "This document is intended for a diverse audience. This includes airport sponsors, airport management, real estate developers, local and regional land use planners..."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 120: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 401.

Authority type: other; as written: FAA Compatibility 3-8; pincite: 3-8.

Cited for: Airport sponsor/manager public outreach and education on compatibility

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: 3.4.3.2: "The airport manager and the airport sponsor may provide the needed education and outreach to the local residents..."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 121: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 423-429.

Authority type: other; as written: FAA Airport Land Use Compatibility Circular ... 1.5.4.3 (FAA Compatibility 1-5); pincite: 1.5.4.3.

Cited for: Protection of approach and departure zones

Quotes: ['1.5.4.3 Protection of Airport Approaches and Departures. The most critical areas surrounding an airport are the approach and departure zones for airport runways...']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: 1.5.4.3: "Protection of Airport Approaches and Departures. The most critical areas surrounding an airport are the approach and departure zones for airport runways... Continually monitoring and evaluating land uses in these areas can ensure the airport continues to operate safely and efficiently."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 122: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 431-437.

Authority type: other; as written: FAA Airport Land Use Compatibility Circular 1.5.4.4.1; pincite: 1.5.4.4.1.

Cited for: Compatibility planning reduces litigation

Quotes: ['Another benefit of compatibility planning is a reduced potential for litigation...']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: 1.5.4.4.1: "Another benefit of compatibility planning is a reduced potential for litigation... Coordinated airport and land use compatibility planning works to prevent potential site development conflicts that could otherwise result in costly and wasteful litigation to prevent incompatible development."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 123: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 439-443.

Authority type: other; as written: FAA Airport Land Use Compatibility Circular (FAA Compatibility 1-5) ... 1.5.6.3.3; pincite: 1.5.6.3.3.

Cited for: Preventing incompatible development is cheaper than mitigation

Quotes: ['Reduced Mitigation Cost for Incompatible Development. It is usually less costly for local jurisdictions to plan and prevent the development of incompatible land uses than to mitigate problems later...']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: 1.5.6.3.3: "Reduced Mitigation Cost for Incompatible Development. It is usually less costly for local jurisdictions to plan and prevent the development of incompatible land uses than to mitigate problems later... In conclusion, when incompatible development is not prevented, higher costs are being incurred locally..."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 124: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 455-459.

Authority type: other; as written: FAA Advisory Circular, 3.6.4.2 (FAA Compatibility 3-11); pincite: 3.6.4.2.

Cited for: FAA funding creates contractual obligation to prevent incompatible development

Quotes: ['FAA funding provides a contractual aspect to land use compatibility', 'an obligation to be vigilant to prevent incompatible development']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Passages appear in AC 150/5190-4B at the cited paragraphs, but the Petition stitches separate sentences or attributes to the airport sponsor wording the AC uses about residents.

Excerpt read: 3.6.4.2: "FAA funding provides a contractual aspect to land use compatibility through the airport sponsor's grant assurance obligations to FAA... as well as an obligation to be vigilant to prevent incompatible development, FAA grant funding can be an important incentive to promote airport land use compatibility..."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 125: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 473.

Authority type: other; as written: FAA Advisory Compatibility Circular, 1.5.4.6.1; pincite: 1.5.4.6.1.

Cited for: Wastewater treatment facilities should be at least 5,000/10,000 feet from runway ends

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: 1.5.4.6.1: "FAA AC 150/5200-33, Hazardous Wildlife Attractants On or Near Airports, advises that specific land use developments such as wastewater treatment facilities, wetlands mitigation, dredge spoil containment areas, and solid waste landfills be located at least 5,000 feet away from the end of a runway at an airport that primarily serves piston-type aircraft..."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 126: FAA Advisory Circular 150/5200-33 series, Hazardous Wildlife Attractants On or Near Airports

Document: 1774361815-petition.docx; location: petition.docx.md line 473 (within AC 150/5190-4B paraphrase).

Authority type: other; as written: (FAA 5200-33), Hazardous Wildlife Attractants on or Near Airports; pincite: .

Cited for: Source of the separation recommendations

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

AC 150/5200-33 (Hazardous Wildlife Attractants On or Near Airports) series exists; 33C is current.

Excerpt read: "150/5200-33C, Hazardous Wildlife Attractants on or near Airports, 2020-02-21"

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150-5200-33C.pdf
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

### Second check: not required


## 127: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 475-479.

Authority type: other; as written: 1.6 Consequences of Incompatible Development (FAA Compatibility 1-9); pincite: 1.6.

Cited for: Incompatible land uses threaten aircraft safety

Quotes: ['Incompatible land uses such as those that pose physical obstructions, create visual distractions, and attract wildlife can threaten the safety of aircraft operations...']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: 1.6.1: "Incompatible land uses such as those that pose physical obstructions, create visual distractions, and attract wildlife can threaten the safety of aircraft operations."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 128: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 481-483.

Authority type: other; as written: 5.3.5.1 (FAA Compatibility 5-17) ... 5.3.5.2; pincite: 5.3.5.1-.2.

Cited for: Conservation easements promote compatibility

Quotes: ['Conservation easements can be adapted to promote airport land use compatibility by limiting the right to develop the property for any incompatible land uses.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: 5.3.5.1-5.3.5.2: "Conservation easements can be adapted to promote airport land use compatibility... Conservation easements are generally best used on agricultural, forest, wetland, scenic, or open space land..."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 129: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 485-489.

Authority type: other; as written: Approach Slopes (14 CFR Part 77) ... (FAA Compatibility p. 104); pincite: p. 104.

Cited for: Precision approach slope ratios

Quotes: ['50:1/40:1 – For all precision instrument runways extending from the primary surface for a distance of 10,000 feet at an approach slope of 50.1 and an additional 40,000 feet beyond this at a 40:1 Approach Slope.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: p.104: "50:1/40:1 – For all precision instrument runways extending from the primary surface for a distance of 10,000 feet at an approach slope of 50.1 and an addi[tional]..."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 130: 14 C.F.R. Part 77

Document: 1774361815-petition.docx; location: petition.docx.md line 485.

Authority type: regulation; as written: 14 CFR Part 77; pincite: .

Cited for: Approach slopes

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 77 is "Safe, Efficient Use, and Preservation of the Navigable Airspace"; its precision approach surface is 50:1 for 10,000 feet then 40:1 for 40,000 feet, as AC 150/5190-4B's glossary summarizes.

Excerpt read: eCFR: "Part 77—Safe, Efficient Use, and Preservation of the Navigable Airspace"; AC 150/5190-4B glossary: "50:1/40:1 – For all precision instrument runways extending from the primary surface for a distance of 10,000 feet..."

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-E/part-77
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 131: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 539-541.

Authority type: other; as written: Appendix D. Example Airport Land Use Compatibility Overlay Zoning Ordinance (FAA Compatibility p. 125); pincite: p. 125.

Cited for: More stringent limitation governs

Quotes: ['the more stringent limitation or requirement shall govern and prevail.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: p.125: "...whether the conflict be with respect to height or structures, the use of land, or any other matter, the more stringent limitation or requirement shall govern and prevail."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 132: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 545.

Authority type: other; as written: FAA Advisory 3.4.3.1 ... 3.4.3.2 (FAA Compatibility 3-8); pincite: 3.4.3.1-.2.

Cited for: Public education and outreach roles of airport manager and sponsor

Quotes: ['Public education about land use compatibility on or near airports will help establish open lines of communication between all parties and set the stage for future dialogues.', 'question the need or purpose of land use development proposals that potentially conflict with airport safety, expand noise exposure']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Passages appear in AC 150/5190-4B at the cited paragraphs, but the Petition stitches separate sentences or attributes to the airport sponsor wording the AC uses about residents.

Excerpt read: 3.4.3.2: "The airport manager and the airport sponsor may provide the needed education and outreach to the local residents... Residents will question the need or purpose of land use development proposals that potentially conflict with airport safety..."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 133: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 549.

Authority type: other; as written: FAA Compatibility Advisory; pincite: .

Cited for: Expectation to establish all necessary protections and exercise zoning controls

Quotes: ['establish all necessary protections', 'exercise zoning controls necessary to prevent any new incompatible land uses']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: Table 2-2: "FAA expects the sponsor to take all appropriate steps available to establish and exercise zoning controls necessary to prevent any new incompatible land uses."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 134: FAA Advisory Circular 150/5190-4B, Airport Land Use Compatibility Planning (Sept. 16, 2022)

Document: 1774361815-petition.docx; location: petition.docx.md line 585-591.

Authority type: other; as written: (2022) FAA Advisory Circular, Airport Land Use Compatibility, No: 150/5190-4B ... Advisory 3.6.7 (FAA Compatibility 3-12); pincite: 3.6.7.

Cited for: Department of the Interior's wildlife responsibilities

Quotes: ['wide range of responsibilities including wildlife (e.g., threatened and endangered species, migratory birds)... (Section 7 consultations under the Endangered Species Act).']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted or paraphrased passage appears in AC 150/5190-4B (Sept. 16, 2022) at the cited paragraph.

Excerpt read: 3.6.7: "DOI has a wide range of responsibilities including wildlife (e.g., threatened and endangered species, migratory birds)... may have a formal role in some situations (e.g. Section 7 consultations under the Endangered Species Act)."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 135: Endangered Species Act s. 7, 16 U.S.C. s. 1536

Document: 1774361815-petition.docx; location: petition.docx.md line 591 (within AC 150/5190-4B quotation).

Authority type: statute; as written: Section 7 consultations under the Endangered Species Act; pincite: .

Cited for: Federal consultation role

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Section 7 of the Endangered Species Act (16 U.S.C. s. 1536, interagency cooperation) is the consultation provision AC 150/5190-4B mentions.

Excerpt read: "16 U.S. Code s. 1536 - Interagency cooperation"

- https://www.law.cornell.edu/uscode/text/16/1536

### Second check: not required


## 136: Lee County LDC s. 34-145(d)

Document: 1774361815-petition.docx; location: petition.docx.md line 403-405.

Authority type: regulation; as written: LDC Section 34-145(d); pincite: 34-145(d).

Cited for: Review criteria for rezonings and planned developments

Quotes: ['a) The proposed use or mix of uses is appropriate at the proposed location; b) The recommended conditions provide sufficient safeguards ...; and c) That each requested deviation: 1) Enhances the achievement of the objectives of the planned development; and 2) Preserves and promotes the general intent of this Code to protect the public health, safety and welfare.']

Context: 

Fictional by design: False; 

### First check: MISQUOTED

The Petition repeats the older 'preserves and promotes' deviation wording. Lee County Ordinance 22-11's redline revised section 34-145(d)(4)a.2.c.2 to 'Protects the public health, safety and welfare'; Ordinance 24-14 later changed another criterion but left this subparagraph unchanged. Thus the 2024 Petition's quote was stale. The precise 2023 codification was not separately retrieved, but the 2022 enacted redline and 2024 amendment history establish the change.

Excerpt read: Ordinance 22-11 page 34 shows the old phrase redlined into 'Protects the public health, safety and welfare'; 24-14 page 44 changes subsection (d)(4)a.1.g only.

- https://www.leegov.com/bocc/Ordinances/22-11.pdf
- https://www.leegov.com/bocc/Ordinances/24-14.pdf

### Second check: pending


## 137: Lee County LDC s. 34-1102

Document: 1774361815-petition.docx; location: petition.docx.md line 407-409.

Authority type: regulation; as written: Lee County LDC Section 34-1102 adopts by reference Florida Statues Chapter 330 and 333 and Federal Regulations and FAA Advisory Circulars; pincite: .

Cited for: Section adopts state statutes, federal regulations and FAA ACs by reference

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

LDC s. 34-1102 is a purpose clause establishing protections "in accordance with" chs. 330 and 333, 14 CFR Parts 77, 150, 151 and ACs 150/5300-13A and 150/5200-33B "as amended, renumbered or replaced". Describing it as adopting those authorities (or federal guidance generally) by reference overstates its text; it does not name AC 150/5190-4B (land use compatibility).

Excerpt read: "The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chs. 330 and 333, as amended, as well as Federal regulations..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 138: Lee County LDC s. 34-1102

Document: 1774361815-petition.docx; location: petition.docx.md line 411-413.

Authority type: regulation; as written: LDC Section 34-1102 (quoted); pincite: .

Cited for: Purpose clause text

Quotes: ['The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chapters 330 and 333, as amended...']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted purpose clause matches current LDC s. 34-1102 (last amended Ord. 19-03, 2019, so unchanged on January 1, 2025); "F.S. Chapters" vs "F.S. Chs." is immaterial.

Excerpt read: "The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chs. 330 and 333, as amended, as well as Federal regulations, as amended, including 14 CFR Parts 77, 150 and 151 and FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced, and 150/5200-33B, as amended, renumbered or replaced..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 139: Fla. Stat. ch. 330

Document: 1774361815-petition.docx; location: petition.docx.md line 411-413 (embedded in quoted LDC s. 34-1102).

Authority type: statute; as written: F.S. Chs. 330; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 330 (Regulation of Aircraft, Pilots, and Airports) exists and is named in LDC s. 34-1102.

Excerpt read: "Chapter 330 REGULATION OF AIRCRAFT, PILOTS, AND AIRPORTS ... 330.35 Airport zoning protection."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0330/0330ContentsIndex.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 140: Fla. Stat. ch. 333

Document: 1774361815-petition.docx; location: petition.docx.md line 411-413 (embedded in quoted LDC s. 34-1102).

Authority type: statute; as written: F.S. Chs. ... 333; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 333 (Airport Zoning) exists and is named in LDC s. 34-1102.

Excerpt read: "Chapter 333 AIRPORT ZONING"

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.01.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 141: 14 C.F.R. Part 77

Document: 1774361815-petition.docx; location: petition.docx.md line 411-413 (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts 77; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 77 is "Safe, Efficient Use, and Preservation of the Navigable Airspace"; its precision approach surface is 50:1 for 10,000 feet then 40:1 for 40,000 feet, as AC 150/5190-4B's glossary summarizes.

Excerpt read: eCFR: "Part 77—Safe, Efficient Use, and Preservation of the Navigable Airspace"; AC 150/5190-4B glossary: "50:1/40:1 – For all precision instrument runways extending from the primary surface for a distance of 10,000 feet..."

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-E/part-77
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 142: 14 C.F.R. Part 150

Document: 1774361815-petition.docx; location: petition.docx.md line 411-413 (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts ... 150; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 150 is "Airport Noise Compatibility Planning."

Excerpt read: "Part 150—Airport Noise Compatibility Planning"

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-I/part-150

### Second check: not required


## 143: 14 C.F.R. Part 151

Document: 1774361815-petition.docx; location: petition.docx.md line 411-413 (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts ... 151; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 151 is "Federal Aid to Airports."

Excerpt read: "Part 151—Federal Aid to Airports"

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-I/part-151

### Second check: not required


## 144: FAA Advisory Circular 150/5300-13A, Airport Design

Document: 1774361815-petition.docx; location: petition.docx.md line 411-413 (embedded in quoted LDC s. 34-1102).

Authority type: other; as written: FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

AC 150/5300-13A, Airport Design (Sept. 28, 2012) exists and is now cancelled (replaced by 150/5300-13B); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Cancelled list: "150/5300-13A ... Airport Design ... 2012-09-28"; current list: "150/5300-13B ... Airport Design - Change 1"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

### Second check: UNABLE_TO_VERIFY

The first reviewer read the FAA current/cancelled index and related code incorporation, but expressly did not read this circular's primary text. Identity evidence does not meet this audit's primary-text requirement for a verified citation. Original first-check explanation: AC 150/5300-13A, Airport Design (Sept. 28, 2012) exists and is now cancelled (replaced by 150/5300-13B); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: Cancelled list: "150/5300-13A ... Airport Design ... 2012-09-28"; current list: "150/5300-13B ... Airport Design - Change 1"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 145: FAA Advisory Circular 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports

Document: 1774361815-petition.docx; location: petition.docx.md line 411-413 (embedded in quoted LDC s. 34-1102).

Authority type: other; as written: 150/5200-33B, as amended, renumbered or replaced; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

AC 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports (Aug. 28, 2007) exists and is now cancelled (replaced by 150/5200-33C); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Cancelled list: "150/5200-33B ... Hazardous Wildlife Attractants On or Near Airports ... 2007-08-28"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

### Second check: UNABLE_TO_VERIFY

The first reviewer read the FAA current/cancelled index and related code incorporation, but expressly did not read this circular's primary text. Identity evidence does not meet this audit's primary-text requirement for a verified citation. Original first-check explanation: AC 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports (Aug. 28, 2007) exists and is now cancelled (replaced by 150/5200-33C); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: Cancelled list: "150/5200-33B ... Hazardous Wildlife Attractants On or Near Airports ... 2007-08-28"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 146: Lee County LDC s. 34-1102

Document: 1774361815-petition.docx; location: petition.docx.md line 413.

Authority type: regulation; as written: LDC Section 34-1102 adopts airport zoning regulations in F.S.§ 333.03(5); pincite: .

Cited for: Section adopts s. 333.03(5) and federal guidance, all deferring to the more stringent requirement

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

LDC s. 34-1102 is a purpose clause establishing protections "in accordance with" chs. 330 and 333, 14 CFR Parts 77, 150, 151 and ACs 150/5300-13A and 150/5200-33B "as amended, renumbered or replaced". Describing it as adopting those authorities (or federal guidance generally) by reference overstates its text; it does not name AC 150/5190-4B (land use compatibility).

Excerpt read: "The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chs. 330 and 333, as amended, as well as Federal regulations..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 147: Fla. Stat. s. 333.03(5) (2023)

Document: 1774361815-petition.docx; location: petition.docx.md line 413.

Authority type: statute; as written: F.S.§ 333.03(5); pincite: 333.03(5).

Cited for: Adopted by LDC 34-1102; defers to more stringent requirement

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The 2023 s. 333.03(5) (renumbered (6) in 2024) permits more restrictive local airport zoning, but LDC s. 34-1102 is a purpose clause that refers to F.S. chs. 330 and 333 "as amended"; it does not expressly adopt s. 333.03(5), and s. 333.03(5) does not say local and federal rules "all defer" to the more stringent requirement (that is s. 333.04(2)).

Excerpt read: LDC 34-1102: "...in accordance with the provisions of F.S. Chs. 330 and 333, as amended..."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2023&URL=0300-0399/0333/Sections/0333.03.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 148: Lee County LDC s. 34-1101

Document: 1774361815-petition.docx; location: petition.docx.md line 415.

Authority type: regulation; as written: Land Development Code Section 34-1101; pincite: 34-1101.

Cited for: Applicability of Airport Compatibility District

Quotes: ['lands encompassing and surrounding facilities operated by the Lee County Port Authority (LCPA) including the Southwest Florida International Airport', 'these provisions are applicable only in the unincorporated areas of Lee County']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

LDC s. 34-1101 contains the first quoted phrase; the second reads "applicable only in the unincorporated portions of Lee County unless an interlocal agreement providing otherwise is in effect" (Petition: "unincorporated areas").

Excerpt read: "The provisions set forth in this division are applicable to lands encompassing and surrounding facilities operated by the Lee County Port Authority (LCPA) including the Southwest Florida International Airport (SWFIA) and Page Field. These provisions are applicable only in the unincorporated portions of Lee County..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 149: Lee County LDC s. 34-1102

Document: 1774361815-petition.docx; location: petition.docx.md line 417-423.

Authority type: regulation; as written: LDC Section 34-1102 (quoted; 'This rezoning violates'); pincite: .

Cited for: Rezoning violates the section

Quotes: ['The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chapters 330 and 333, as amended...']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted purpose clause matches current LDC s. 34-1102 (last amended Ord. 19-03, 2019, so unchanged on January 1, 2025); "F.S. Chapters" vs "F.S. Chs." is immaterial.

Excerpt read: "The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chs. 330 and 333, as amended, as well as Federal regulations, as amended, including 14 CFR Parts 77, 150 and 151 and FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced, and 150/5200-33B, as amended, renumbered or replaced..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 150: Fla. Stat. ch. 330

Document: 1774361815-petition.docx; location: petition.docx.md line 419-423 (embedded in quoted LDC s. 34-1102).

Authority type: statute; as written: F.S. Chs. 330; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 330 (Regulation of Aircraft, Pilots, and Airports) exists and is named in LDC s. 34-1102.

Excerpt read: "Chapter 330 REGULATION OF AIRCRAFT, PILOTS, AND AIRPORTS ... 330.35 Airport zoning protection."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0330/0330ContentsIndex.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 151: Fla. Stat. ch. 333

Document: 1774361815-petition.docx; location: petition.docx.md line 419-423 (embedded in quoted LDC s. 34-1102).

Authority type: statute; as written: F.S. Chs. ... 333; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 333 (Airport Zoning) exists and is named in LDC s. 34-1102.

Excerpt read: "Chapter 333 AIRPORT ZONING"

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.01.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 152: 14 C.F.R. Part 77

Document: 1774361815-petition.docx; location: petition.docx.md line 419-423 (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts 77; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 77 is "Safe, Efficient Use, and Preservation of the Navigable Airspace"; its precision approach surface is 50:1 for 10,000 feet then 40:1 for 40,000 feet, as AC 150/5190-4B's glossary summarizes.

Excerpt read: eCFR: "Part 77—Safe, Efficient Use, and Preservation of the Navigable Airspace"; AC 150/5190-4B glossary: "50:1/40:1 – For all precision instrument runways extending from the primary surface for a distance of 10,000 feet..."

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-E/part-77
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 153: 14 C.F.R. Part 150

Document: 1774361815-petition.docx; location: petition.docx.md line 419-423 (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts ... 150; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 150 is "Airport Noise Compatibility Planning."

Excerpt read: "Part 150—Airport Noise Compatibility Planning"

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-I/part-150

### Second check: not required


## 154: 14 C.F.R. Part 151

Document: 1774361815-petition.docx; location: petition.docx.md line 419-423 (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts ... 151; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 151 is "Federal Aid to Airports."

Excerpt read: "Part 151—Federal Aid to Airports"

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-I/part-151

### Second check: not required


## 155: FAA Advisory Circular 150/5300-13A, Airport Design

Document: 1774361815-petition.docx; location: petition.docx.md line 419-423 (embedded in quoted LDC s. 34-1102).

Authority type: other; as written: FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

AC 150/5300-13A, Airport Design (Sept. 28, 2012) exists and is now cancelled (replaced by 150/5300-13B); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Cancelled list: "150/5300-13A ... Airport Design ... 2012-09-28"; current list: "150/5300-13B ... Airport Design - Change 1"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

### Second check: UNABLE_TO_VERIFY

The first reviewer read the FAA current/cancelled index and related code incorporation, but expressly did not read this circular's primary text. Identity evidence does not meet this audit's primary-text requirement for a verified citation. Original first-check explanation: AC 150/5300-13A, Airport Design (Sept. 28, 2012) exists and is now cancelled (replaced by 150/5300-13B); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: Cancelled list: "150/5300-13A ... Airport Design ... 2012-09-28"; current list: "150/5300-13B ... Airport Design - Change 1"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 156: FAA Advisory Circular 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports

Document: 1774361815-petition.docx; location: petition.docx.md line 419-423 (embedded in quoted LDC s. 34-1102).

Authority type: other; as written: 150/5200-33B, as amended, renumbered or replaced; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

AC 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports (Aug. 28, 2007) exists and is now cancelled (replaced by 150/5200-33C); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Cancelled list: "150/5200-33B ... Hazardous Wildlife Attractants On or Near Airports ... 2007-08-28"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

### Second check: UNABLE_TO_VERIFY

The first reviewer read the FAA current/cancelled index and related code incorporation, but expressly did not read this circular's primary text. Identity evidence does not meet this audit's primary-text requirement for a verified citation. Original first-check explanation: AC 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports (Aug. 28, 2007) exists and is now cancelled (replaced by 150/5200-33C); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: Cancelled list: "150/5200-33B ... Hazardous Wildlife Attractants On or Near Airports ... 2007-08-28"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 157: Fla. Stat. s. 333.01(5), (8)

Document: 1774361815-petition.docx; location: petition.docx.md line 445.

Authority type: statute; as written: Florida Statutes § 333.01(5) and §333.01(8); pincite: (5), (8).

Cited for: Definitions of airport land use compatibility zoning and airport protection zoning regulations

Quotes: ['Airport land use compatibility zoning means airport zoning regulations governing the use of land on, adjacent to, or in the immediate vicinity of airports', 'Airport protection zoning regulations means airport zoning regulations governing airport hazards']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Both definitions are quoted accurately from s. 333.01(5) and (8) (2024).

Excerpt read: "(5) 'Airport land use compatibility zoning' means airport zoning regulations governing the use of land on, adjacent to, or in the immediate vicinity of airports... (8) 'Airport protection zoning regulations' means airport zoning regulations governing airport hazards."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.01.html

### Second check: not required


## 158: Fla. Stat. s. 333.02(1)

Document: 1774361815-petition.docx; location: petition.docx.md line 447-449.

Authority type: statute; as written: Florida Statutes § 333.02; pincite: .

Cited for: Legislative findings on airport hazards and incompatible uses

Quotes: ['(1) It is hereby found that an airport hazard endangers the lives and property of users of the airport and of occupants of land in its vicinity...']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Section 333.02(1) quoted accurately (2024); the quoted text itself cross-refers to s. 333.03(2).

Excerpt read: "(1) It is hereby found that an airport hazard endangers the lives and property of users of the airport ... as enumerated in s. 333.03(2) are not compatible with normal airport operations..."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.02.html

### Second check: not required


## 159: Fla. Stat. s. 333.03(2)

Document: 1774361815-petition.docx; location: petition.docx.md line 449 (within s. 333.02 quotation).

Authority type: statute; as written: F.S.§ 333.03(2); pincite: 333.03(2).

Cited for: Enumerated incompatible activities and uses

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Section 333.03(2) requires political subdivisions to adopt airport land use compatibility zoning regulations and enumerates minimum subjects; it is the cross-reference embedded in s. 333.02(1).

Excerpt read: "(2) In the manner provided in subsection (1), political subdivisions shall adopt, administer, and enforce airport land use compatibility zoning regulations. At a minimum, airport land use compatibility zoning regulations must address the following..."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.03.html

### Second check: not required


## 160: Fla. Stat. s. 333.02(1)(a)

Document: 1774361815-petition.docx; location: petition.docx.md line 451.

Authority type: statute; as written: F.S.§ 333.02(a); pincite: 333.02(a).

Cited for: Incompatible land uses are public nuisances

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The public-nuisance and prevention declarations are in s. 333.02(1)(a) and (1)(b); the Petition cites "333.02(a)" and "333.02(b)", omitting subsection (1). Substance accurate.

Excerpt read: "(a) That the creation or establishment of an airport hazard and the incompatible use of land in airport vicinities are public nuisances ... (b) That it is therefore necessary in the interest of the public health, public safety, and general welfare that the creation or establishment of airport hazards and incompatible land uses be prevented"

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.02.html

### Second check: not required


## 161: Fla. Stat. s. 333.02(1)(b)

Document: 1774361815-petition.docx; location: petition.docx.md line 451.

Authority type: statute; as written: § 333.02(b); pincite: 333.02(b).

Cited for: Incompatible land uses should be prevented

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The public-nuisance and prevention declarations are in s. 333.02(1)(a) and (1)(b); the Petition cites "333.02(a)" and "333.02(b)", omitting subsection (1). Substance accurate.

Excerpt read: "(a) That the creation or establishment of an airport hazard and the incompatible use of land in airport vicinities are public nuisances ... (b) That it is therefore necessary in the interest of the public health, public safety, and general welfare that the creation or establishment of airport hazards and incompatible land uses be prevented"

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.02.html

### Second check: not required


## 162: Fla. Stat. s. 333.02(2)

Document: 1774361815-petition.docx; location: petition.docx.md line 451-453.

Authority type: statute; as written: F.S.§ 333.02(2); pincite: 333.02(2).

Cited for: Political subdivisions may expend funds and acquire land to limit incompatible uses

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Section 333.02(2) declares that limiting incompatible land uses is a public purpose for which political subdivisions may raise and expend funds and acquire land.

Excerpt read: "(2) It is further declared that the limitation of land uses incompatible with normal airport operations ... are public purposes for which political subdivisions may raise and expend public funds and acquire land or property interests therein"

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.02.html

### Second check: not required


## 163: Fla. Stat. s. 333.03(5) (2023)

Document: 1774361815-petition.docx; location: petition.docx.md line 461.

Authority type: statute; as written: F.S.§ 333.03(5); pincite: 333.03(5).

Cited for: Permits more restrictive local airport zoning

Quotes: ['does not prohibit an airport authority, a political subdivision or its administrative agency, or any other governing body operating a public-use airport from establishing airport zoning regulations more restrictive than prescribed in this section in order to protect the health, safety, and welfare of the public in the air and on the ground.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

In the 2023 statutes (in force when the Petition was filed, February 2024) the quoted language was s. 333.03(5); a 2024 amendment renumbered it s. 333.03(6), the version in effect on January 1, 2025. Quote accurate.

Excerpt read: 2023 s.333.03(5): "This section does not prohibit an airport authority, a political subdivision or its administrative agency, or any other governing body operating a public-use airport from establishing airport zoning regulations more restrictive than prescribed in this section in order to protect the health, safety, and welfare of the public in the air and on the ground."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2023&URL=0300-0399/0333/Sections/0333.03.html
- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.03.html

### Second check: not required


## 164: Lee County LDC s. 34-1102

Document: 1774361815-petition.docx; location: petition.docx.md line 461.

Authority type: regulation; as written: LDC Section 34-1102; pincite: .

Cited for: Requirement in 34-1102 to adopt airport zoning regulations in s. 333.03(5)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

LDC s. 34-1102 is a purpose clause establishing protections "in accordance with" chs. 330 and 333, 14 CFR Parts 77, 150, 151 and ACs 150/5300-13A and 150/5200-33B "as amended, renumbered or replaced". Describing it as adopting those authorities (or federal guidance generally) by reference overstates its text; it does not name AC 150/5190-4B (land use compatibility).

Excerpt read: "The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chs. 330 and 333, as amended, as well as Federal regulations..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 165: Fla. Stat. s. 333.04(2)

Document: 1774361815-petition.docx; location: petition.docx.md line 463-465.

Authority type: statute; as written: F.S.§ 333.04(2); pincite: 333.04(2).

Cited for: More stringent requirement prevails in a conflict

Quotes: ['In the event of conflict between any airport zoning regulations adopted under this chapter and any other regulations applicable to the same area ... the more stringent limitation or requirement shall govern and prevail.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Section 333.04(2) quoted accurately (2024): in a conflict the more stringent limitation or requirement governs.

Excerpt read: "(2) CONFLICT.—In the event of conflict between any airport zoning regulations adopted under this chapter and any other regulations applicable to the same area ... the more stringent limitation or requirement shall govern and prevail."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.04.html

### Second check: not required


## 166: Fla. Stat. s. 333.06

Document: 1774361815-petition.docx; location: petition.docx.md line 471.

Authority type: statute; as written: F.S.§ 333.06; pincite: 333.06.

Cited for: Rezoning to wastewater use is incompatible under s. 333.06

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Section 333.06 sets requirements (reasonableness, independent justification, runway protection zones) for airport zoning regulations that political subdivisions adopt; it does not itself declare a particular rezoning incompatible. Cited loosely.

Excerpt read: "333.06 Airport zoning regulation requirements.—(1) REASONABLENESS.—All airport zoning regulations adopted under this chapter shall be reasonable..."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.06.html

### Second check: not required


## 167: Fla. Stat. s. 333.06(2)

Document: 1774361815-petition.docx; location: petition.docx.md line 471.

Authority type: statute; as written: F.S.§ 333.06(2); pincite: 333.06(2).

Cited for: Independent justification; LDC adopts it by reference

Quotes: ['The purpose of all airport zoning regulations adopted under this chapter is to provide both airspace protection and land uses compatible with airport operations. Each aspect of this purpose requires independent justification in order to promote the public interest in safety, health, and general welfare.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Section 333.06(2) quoted accurately (2024). The Petition's statement that the LDC "adopts by reference" this subsection rests on LDC s. 34-1102's general reference to ch. 333.

Excerpt read: "(2) INDEPENDENT JUSTIFICATION.—The purpose of all airport zoning regulations adopted under this chapter is to provide both airspace protection and land uses compatible with airport operations. Each aspect of this purpose requires independent justification in order to promote the public interest in safety, health, and general welfare."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.06.html

### Second check: not required


## 168: FAA Advisory Circular 150/5200-33C, Hazardous Wildlife Attractants on or near Airports (Feb. 21, 2020)

Document: 1774361815-petition.docx; location: petition.docx.md line 491-497.

Authority type: other; as written: FAA Advisory Circular 150/5200-33C, Hazardous Wildlife Attractants on or near Airports February 21, 2020, 1.4; pincite: 1.4.

Cited for: FAA recommends 5-mile separation from aircraft operations area

Quotes: ["For all airports, the FAA recommends a distance of 5 miles between the closest point of the airport's aircraft operations area and the hazardous wildlife attractant."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted passage appears in AC 150/5200-33C (Feb. 21, 2020) at the cited paragraph.

Excerpt read: 1.4: "For all airports, the FAA recommends a distance of 5 miles between the closest point of the airport's aircraft operations area and the hazardous wildlife attractant."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150-5200-33C.pdf

### Second check: not required


## 169: FAA Advisory Circular 150/5200-33B (as captioned; figure matches 150/5200-33C)

Document: 1774361815-petition.docx; location: petition.docx.md line 503 (figure caption).

Authority type: other; as written: Figure 1, FAA Advisory Circular 150/5200 – 33B; pincite: Fig. 1.

Cited for: Recommended separation perimeters

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The reproduced Figure 1 and Perimeter A/B/C text match AC 150/5200-33C (2020) p.1-3 ("it is recommended"); the caption attributes it to AC 150/5200-33B. AC 150/5200-33B (2007, now cancelled) was not read.

Excerpt read: 33C p.1-3: "Figure 1. Example of recommended separation distances described in Chapter 1 ... PERIMETER A: For airports serving piston-powered aircraft, it is recommended hazardous wildlife attractants be 5,000 feet from the nearest aircraft operations area."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150-5200-33C.pdf
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3

### Second check: not required


## 170: FAA Advisory Circular 150/5200-33C, Hazardous Wildlife Attractants on or near Airports (Feb. 21, 2020)

Document: 1774361815-petition.docx; location: petition.docx.md line 521-525.

Authority type: other; as written: 4.4 Coordination to Prevent Creation of New Off-Airport Hazardous Wildlife Attractants (FAA Attractants, p. 48); pincite: 4.4.

Cited for: Airport operators should watch for proposed wastewater facilities

Quotes: ['Airport operators should work with local and regional planning and zoning boards ... Pay particular attention to proposed land uses involving creation or expansion of wastewater treatment facilities...']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted passage appears in AC 150/5200-33C (Feb. 21, 2020) at the cited paragraph.

Excerpt read: 4.4: "Airport operators should work with local and regional planning and zoning boards to be aware of proposed land-use changes... Pay particular attention to proposed land uses involving creation or expansion of wastewater treatment facilities..."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150-5200-33C.pdf

### Second check: not required


## 171: FAA Advisory Circular 150/5200-33C, Hazardous Wildlife Attractants on or near Airports (Feb. 21, 2020)

Document: 1774361815-petition.docx; location: petition.docx.md line 527-533.

Authority type: other; as written: 2.3.4 New Wastewater Treatment Facilities (FAA Attractants p. 17); pincite: 2.3.4.

Cited for: FAA recommends against new wastewater treatment facilities within the separations

Quotes: ['The FAA recommends against the construction of new wastewater treatment facilities or associated settling ponds within the separations identified in Paragraphs 1.2 through 1.4.', 'any devices and/or systems used to store, treat, recycle, or reclaim municipal sewage or liquid industrial wastes.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted passage appears in AC 150/5200-33C (Feb. 21, 2020) at the cited paragraph.

Excerpt read: 2.3.4: "The FAA recommends against the construction of new wastewater treatment facilities or associated settling ponds within the separations identified in Paragraphs 1.2 through 1.4. Appendix 1 defines wastewater treatment facility as 'any devices and/or systems used to store, treat, recycle, or reclaim municipal sewage or liquid industrial wastes.'"

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150-5200-33C.pdf

### Second check: not required


## 172: FAA Advisory Circular 150/5200-33C, Hazardous Wildlife Attractants on or near Airports (Feb. 21, 2020)

Document: 1774361815-petition.docx; location: petition.docx.md line 535-537.

Authority type: other; as written: Continuing [2.3.4]; pincite: 2.3.4.

Cited for: A more suitable location should be identified if possible

Quotes: ['When a wastewater treatment facility is proposed within the separation criteria ... If possible, a more suitable location for the proposed facility should be identified.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted passage appears in AC 150/5200-33C (Feb. 21, 2020) at the cited paragraph.

Excerpt read: 2.3.4: "When a wastewater treatment facility is proposed within the separation criteria, the airport operator, project proponent, and local jurisdiction should discuss the proposed project location ... If possible, a more suitable location for the proposed facility should be identified."

- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150-5200-33C.pdf

### Second check: not required


## 173: Lee County LDC s. 34-1102

Document: 1774361815-petition.docx; location: petition.docx.md line 543.

Authority type: regulation; as written: LDC Section 34-1102 adopts airport zoning regulations in F.S.§ 333.03(5); pincite: .

Cited for: Same as line 413

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

LDC s. 34-1102 is a purpose clause establishing protections "in accordance with" chs. 330 and 333, 14 CFR Parts 77, 150, 151 and ACs 150/5300-13A and 150/5200-33B "as amended, renumbered or replaced". Describing it as adopting those authorities (or federal guidance generally) by reference overstates its text; it does not name AC 150/5190-4B (land use compatibility).

Excerpt read: "The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chs. 330 and 333, as amended, as well as Federal regulations..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 174: Fla. Stat. s. 333.03(5) (2023)

Document: 1774361815-petition.docx; location: petition.docx.md line 543.

Authority type: statute; as written: F.S.§ 333.03(5); pincite: 333.03(5).

Cited for: Adopted by LDC 34-1102

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The 2023 s. 333.03(5) (renumbered (6) in 2024) permits more restrictive local airport zoning, but LDC s. 34-1102 is a purpose clause that refers to F.S. chs. 330 and 333 "as amended"; it does not expressly adopt s. 333.03(5), and s. 333.03(5) does not say local and federal rules "all defer" to the more stringent requirement (that is s. 333.04(2)).

Excerpt read: LDC 34-1102: "...in accordance with the provisions of F.S. Chs. 330 and 333, as amended..."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2023&URL=0300-0399/0333/Sections/0333.03.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 175: Lee County LDC s. 34-1101

Document: 1774361815-petition.docx; location: petition.docx.md line 577-579.

Authority type: regulation; as written: Land Development Code Section 34-1101; pincite: 34-1101.

Cited for: Applicability of Airport Compatibility District (repeated)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

LDC s. 34-1101 contains the first quoted phrase; the second reads "applicable only in the unincorporated portions of Lee County unless an interlocal agreement providing otherwise is in effect" (Petition: "unincorporated areas").

Excerpt read: "The provisions set forth in this division are applicable to lands encompassing and surrounding facilities operated by the Lee County Port Authority (LCPA) including the Southwest Florida International Airport (SWFIA) and Page Field. These provisions are applicable only in the unincorporated portions of Lee County..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 176: Lee County LDC s. 34-1102

Document: 1774361815-petition.docx; location: petition.docx.md line 579-583.

Authority type: regulation; as written: LDC Section 34-1102 details:; pincite: .

Cited for: Purpose clause text (wildlife attractants)

Quotes: ['The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chapters 330 and 333, as amended...']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted purpose clause matches current LDC s. 34-1102 (last amended Ord. 19-03, 2019, so unchanged on January 1, 2025); "F.S. Chapters" vs "F.S. Chs." is immaterial.

Excerpt read: "The purpose of this division is to establish protections around SWFIA and Page Field in accordance with the provisions of F.S. Chs. 330 and 333, as amended, as well as Federal regulations, as amended, including 14 CFR Parts 77, 150 and 151 and FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced, and 150/5200-33B, as amended, renumbered or replaced..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 177: Fla. Stat. ch. 330

Document: 1774361815-petition.docx; location: petition.docx.md line 581-583 (embedded in quoted LDC s. 34-1102).

Authority type: statute; as written: F.S. Chs. 330; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 330 (Regulation of Aircraft, Pilots, and Airports) exists and is named in LDC s. 34-1102.

Excerpt read: "Chapter 330 REGULATION OF AIRCRAFT, PILOTS, AND AIRPORTS ... 330.35 Airport zoning protection."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0330/0330ContentsIndex.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 178: Fla. Stat. ch. 333

Document: 1774361815-petition.docx; location: petition.docx.md line 581-583 (embedded in quoted LDC s. 34-1102).

Authority type: statute; as written: F.S. Chs. ... 333; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 333 (Airport Zoning) exists and is named in LDC s. 34-1102.

Excerpt read: "Chapter 333 AIRPORT ZONING"

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0300-0399/0333/Sections/0333.01.html
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV12AICODI_S34-1102PUIN

### Second check: not required


## 179: 14 C.F.R. Part 77

Document: 1774361815-petition.docx; location: petition.docx.md line 581-583 (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts 77; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 77 is "Safe, Efficient Use, and Preservation of the Navigable Airspace"; its precision approach surface is 50:1 for 10,000 feet then 40:1 for 40,000 feet, as AC 150/5190-4B's glossary summarizes.

Excerpt read: eCFR: "Part 77—Safe, Efficient Use, and Preservation of the Navigable Airspace"; AC 150/5190-4B glossary: "50:1/40:1 – For all precision instrument runways extending from the primary surface for a distance of 10,000 feet..."

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-E/part-77
- https://www.faa.gov/documentLibrary/media/Advisory_Circular/150_5190_4b_Land_Use_Compatibility.pdf

### Second check: not required


## 180: 14 C.F.R. Part 150

Document: 1774361815-petition.docx; location: petition.docx.md line 581-583 (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts ... 150; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 150 is "Airport Noise Compatibility Planning."

Excerpt read: "Part 150—Airport Noise Compatibility Planning"

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-I/part-150

### Second check: not required


## 181: 14 C.F.R. Part 151

Document: 1774361815-petition.docx; location: petition.docx.md line 581-583 (embedded in quoted LDC s. 34-1102).

Authority type: regulation; as written: 14 CFR Parts ... 151; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

14 CFR Part 151 is "Federal Aid to Airports."

Excerpt read: "Part 151—Federal Aid to Airports"

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-I/part-151

### Second check: not required


## 182: FAA Advisory Circular 150/5300-13A, Airport Design

Document: 1774361815-petition.docx; location: petition.docx.md line 581-583 (embedded in quoted LDC s. 34-1102).

Authority type: other; as written: FAA Advisory Circulars 150/5300-13A, as amended, renumbered or replaced; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

AC 150/5300-13A, Airport Design (Sept. 28, 2012) exists and is now cancelled (replaced by 150/5300-13B); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Cancelled list: "150/5300-13A ... Airport Design ... 2012-09-28"; current list: "150/5300-13B ... Airport Design - Change 1"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

### Second check: UNABLE_TO_VERIFY

The first reviewer read the FAA current/cancelled index and related code incorporation, but expressly did not read this circular's primary text. Identity evidence does not meet this audit's primary-text requirement for a verified citation. Original first-check explanation: AC 150/5300-13A, Airport Design (Sept. 28, 2012) exists and is now cancelled (replaced by 150/5300-13B); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: Cancelled list: "150/5300-13A ... Airport Design ... 2012-09-28"; current list: "150/5300-13B ... Airport Design - Change 1"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 183: FAA Advisory Circular 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports

Document: 1774361815-petition.docx; location: petition.docx.md line 581-583 (embedded in quoted LDC s. 34-1102).

Authority type: other; as written: 150/5200-33B, as amended, renumbered or replaced; pincite: .

Cited for: Authority named in LDC s. 34-1102's purpose clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

AC 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports (Aug. 28, 2007) exists and is now cancelled (replaced by 150/5200-33C); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Cancelled list: "150/5200-33B ... Hazardous Wildlife Attractants On or Near Airports ... 2007-08-28"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

### Second check: UNABLE_TO_VERIFY

The first reviewer read the FAA current/cancelled index and related code incorporation, but expressly did not read this circular's primary text. Identity evidence does not meet this audit's primary-text requirement for a verified citation. Original first-check explanation: AC 150/5200-33B, Hazardous Wildlife Attractants On or Near Airports (Aug. 28, 2007) exists and is now cancelled (replaced by 150/5200-33C); the LDC names it "as amended, renumbered or replaced."

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: Cancelled list: "150/5200-33B ... Hazardous Wildlife Attractants On or Near Airports ... 2007-08-28"

- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/3
- https://www.faa.gov/airports/resources/advisory_circulars/index.cfm/go/document.exportAll/statusID/2

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 184: Lee County LDC s. 10-473

Document: 1774361815-petition.docx; location: petition.docx.md line 593-597.

Authority type: regulation; as written: LEE COUNTY LAND DEVELOPMENT CODE, Sec. 10-473; pincite: 10-473.

Cited for: Listed-species survey required for planned development rezonings

Quotes: ['a survey must accompany all planned development rezoning applications', 'indicate a possible presence of a Lee County listed species', 'such survey must include Lee County listed species presence (sightings, signs, tracks, trails, nests, evidence of feeding, etc.), population estimates and occupied habitat boundaries']

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-473(a) quoted accurately (last amended 1996).

Excerpt read: "A survey must accompany all planned development rezoning applications ... where the Florida Land Use, Cover and Forms Classification System codes for the property indicate a possible presence of a Lee County listed species... Such survey must include Lee County listed species presence (sightings, signs, tracks, trails, nests, evidence of feeding, etc.), population estimates and occupied habitat boundaries."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: not required


## 185: Lee County LDC s. 10-474

Document: 1774361815-petition.docx; location: petition.docx.md line 599-601.

Authority type: regulation; as written: Section 10-474; pincite: 10-474.

Cited for: Management plan required if listed species found

Quotes: ['if listed species are found on the property']

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-473(b) requires a management plan meeting s. 10-474 if listed species are found, and s. 10-474 lists "Consideration of Game Commission guidelines for listed species" among plan components.

Excerpt read: "A management plan meeting the requirements of Section 10-474 will be required for all development order applications if listed species are found on the property"; s.10-474: "Consideration of Game Commission guidelines for listed species. In cases where guidelines have been prepared by the Game Commission for a listed species, those guidelines must be considered..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: not required


## 186: Lee County LDC s. 10-474

Document: 1774361815-petition.docx; location: petition.docx.md line 601.

Authority type: regulation; as written: Sec. 10-474; pincite: 10-474.

Cited for: Management plans consider Game Commission guidelines

Quotes: ['Consideration of Game Commission guidelines for listed species.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-473(b) requires a management plan meeting s. 10-474 if listed species are found, and s. 10-474 lists "Consideration of Game Commission guidelines for listed species" among plan components.

Excerpt read: "A management plan meeting the requirements of Section 10-474 will be required for all development order applications if listed species are found on the property"; s.10-474: "Consideration of Game Commission guidelines for listed species. In cases where guidelines have been prepared by the Game Commission for a listed species, those guidelines must be considered..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: not required


## 187: Clean Water Act s. 404, 33 U.S.C. s. 1344

Document: 1774361815-petition.docx; location: petition.docx.md line 607-609 (within quoted Biological Opinion).

Authority type: statute; as written: Section 404 of the Clean Water Act; pincite: .

Cited for: Corps wetland fill permit triggering consultation

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Section 404 of the Clean Water Act (33 U.S.C. s. 1344) governs permits for dredged or fill material, as the quoted biological opinion describes.

Excerpt read: "33 U.S. Code s. 1344 - Permits for dredged or fill material"

- https://www.law.cornell.edu/uscode/text/33/1344

### Second check: not required


## 188: 50 C.F.R. s. 402.16 (2017)

Document: 1774361815-petition.docx; location: petition.docx.md line 613 (within quoted Biological Opinion).

Authority type: regulation; as written: 50 CFR § 402.16; pincite: 402.16.

Cited for: Conditions requiring reinitiation of formal consultation

Quotes: ['As provided in 50 CFR § 402.16, reinitiation of formal consultation is required where discretionary Federal agency involvement or control over the action has been retained (or is authorized by law) and if: (I) the amount or extent of incidental take is exceeded...']

Context: 

Fictional by design: False; 

### First check: VERIFIED

The 2017 text of 50 CFR 402.16 lists the four reinitiation triggers the quoted biological opinion paraphrases (order of two triggers differs).

Excerpt read: "Reinitiation of formal consultation is required ... (a) If the amount or extent of taking specified in the incidental take statement is exceeded; (b) If new information reveals effects of the action ... (c) If the identified action is subsequently modified ... (d) If a new species is listed or critical habitat designated..."

- https://www.ecfr.gov/api/versioner/v1/full/2017-06-01/title-50.xml?part=402&section=402.16

### Second check: not required


## 189: Fla. Stat. s. 163.3177(6)(d)1.a (cited as 163.3177(1))

Document: 1774361815-petition.docx; location: petition.docx.md line 619.

Authority type: statute; as written: F.S.§ 163.3177(1); pincite: 163.3177(1).

Cited for: Natural resources must be identified and analyzed

Quotes: ["where present within the local government's boundaries, shall be identified and analyzed and existing recreational or conservation uses, known pollution problems, including hazardous wastes, and the potential for conservation, recreation, use, or protection shall also be identified: a. Rivers, bays, lakes, wetlands including estuarine marshes, groundwaters, and springs, including information on quality of the resource available."]

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

The quoted natural-resources language is s. 163.3177(6)(d)1.a (conservation element), not s. 163.3177(1). Real statute, wrong subsection. It also prescribes comprehensive-plan content, not rezoning criteria.

Excerpt read: "(d) A conservation element ... 1. The following natural resources, where present within the local government's boundaries, shall be identified and analyzed and existing recreational or conservation uses, known pollution problems, including hazardous wastes, and the potential for conservation, recreation, use, or protection shall also be identified: a. Rivers, bays, lakes, wetlands including estuarine marshes, groundwaters, and springs, including information on quality of the resource available."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0100-0199/0163/Sections/0163.3177.html

### Second check: WRONG_CITATION_REAL_CASE

The natural-resources inventory language quoted in the Petition is in section 163.3177(6)(d)1.a, the conservation element, not subsection (1). It governs comprehensive-plan contents rather than independently providing a rezoning approval criterion.

Excerpt read: Subsection (6)(d)1.a describes identification and analysis of natural resources in the conservation element.

- https://www.flsenate.gov/Laws/Statutes/2024/163.3177

Model: gpt-6-sol; reasoning effort: high.

## 190: Fla. Stat. s. 163.3177(6)(d)2.b (cited as 163.3177(b))

Document: 1774361815-petition.docx; location: petition.docx.md line 619.

Authority type: statute; as written: F.S.§ 163.3177(b); pincite: 163.3177(b).

Cited for: Conserve and protect water sources including recharge and wellhead areas

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The paraphrased text is s. 163.3177(6)(d)2.b ("... and surface waters used as a source of public water supply"). The Petition's "163.3177(b)" omits the (6)(d)2 hierarchy; it is a comprehensive-plan content requirement.

Excerpt read: "b. Conserves, appropriately uses, and protects the quality and quantity of current and projected water sources and waters that flow into estuarine waters or oceanic waters ... including natural groundwater recharge areas, wellhead protection areas, and surface waters used as a source of public water supply."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0100-0199/0163/Sections/0163.3177.html

### Second check: not required


## 191: Lee County Code of Ordinances s. 11-21 (labeled LDC)

Document: 1774361815-petition.docx; location: petition.docx.md line 647-649.

Authority type: regulation; as written: Lee County Land Development Code, Article II., Water Conservation, Sec. 11-21.; pincite: 11-21.

Cited for: Purpose and territorial scope of water conservation article

Quotes: ["to protect Lee County's water resources from the harmful effects of over utilization throughout the year, as well as during periods of water shortage...", 'The territorial scope and provisions of this article shall apply to all persons using water resources, whether from public or privately owned water utility systems, private wells...']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Section 11-21 is in the Lee County Code of Ordinances (ch. 11, Water Conservation Ordinance), not the Land Development Code as the Petition labels it. Quotations of (b) and (c) are accurate.

Excerpt read: "(b) The purpose of this article is to protect Lee County's water resources from the harmful effects of over utilization ... provided in F.A.C. Chs. 40E-21 and 40E-24, as may be amended from time to time."

- https://library.municode.com/fl/lee_county/codes/code_of_ordinances?nodeId=PTIICOOR_CH11ENNARE

### Second check: not required


## 192: Fla. Admin. Code ch. 40E-21

Document: 1774361815-petition.docx; location: petition.docx.md line 647-649 (within s. 11-21 quotation).

Authority type: regulation; as written: F.A.C. Chapters. 40E-21; pincite: .

Cited for: SFWMD Water Shortage Plan

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 40E-21, F.A.C. is the SFWMD Water Shortage Plan.

Excerpt read: "Chapter Title: WATER SHORTAGE PLAN"

- https://www.flrules.org/gateway/ChapterHome.asp?Chapter=40E-21

### Second check: not required


## 193: Fla. Admin. Code ch. 40E-24

Document: 1774361815-petition.docx; location: petition.docx.md line 647-649 (within s. 11-21 quotation).

Authority type: regulation; as written: F.A.C. ... 40E-24; pincite: .

Cited for: Mandatory year-round landscape irrigation measures

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 40E-24, F.A.C. is the Mandatory Year-Round Landscape Irrigation Conservation Measures rule.

Excerpt read: "Chapter Title: MANDATORY YEAR-ROUND LANDSCAPE IRRIGATION MEASURES CONSERVATION MEASURES"

- https://www.flrules.org/gateway/ChapterHome.asp?Chapter=40E-24

### Second check: not required


## 194: Fla. Admin. Code ch. 40E-24

Document: 1774361815-petition.docx; location: petition.docx.md line 649 (within s. 11-21 quotation).

Authority type: regulation; as written: F.A.C. Ch. 40E-24; pincite: .

Cited for: Exemptions from water conservation article

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 40E-24, F.A.C. is the Mandatory Year-Round Landscape Irrigation Conservation Measures rule.

Excerpt read: "Chapter Title: MANDATORY YEAR-ROUND LANDSCAPE IRRIGATION MEASURES CONSERVATION MEASURES"

- https://www.flrules.org/gateway/ChapterHome.asp?Chapter=40E-24

### Second check: not required


## 195: Fla. Stat. s. 163.3177(6)(d)2.k (cited as 163.3177(k))

Document: 1774361815-petition.docx; location: petition.docx.md line 659.

Authority type: statute; as written: F.S.§ 163.3177(k); pincite: 163.3177(k).

Cited for: Direct incompatible land uses away from wetlands

Quotes: ['Directs future land uses that are incompatible with the protection and conservation of wetlands and wetland functions away from wetlands. The type, intensity or density, extent, distribution, and location of allowable land uses and the types, values, functions, sizes, conditions and locations of wetlands are land use factors that shall be considered when directing incompatible land uses away from wetlands.']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Quoted text is s. 163.3177(6)(d)2.k, accurately quoted; the Petition's "163.3177(k)" omits the (6)(d)2 hierarchy. A comprehensive-plan content requirement.

Excerpt read: "k. Directs future land uses that are incompatible with the protection and conservation of wetlands and wetland functions away from wetlands. The type, intensity or density, extent, distribution, and location of allowable land uses and the types, values, functions, sizes, conditions, and locations of wetlands are land use factors that shall be considered..."

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0100-0199/0163/Sections/0163.3177.html

### Second check: not required


## 196: Lee County LDC s. 34-411(g), (i)

Document: 1774361815-petition.docx; location: petition.docx.md line 691-695.

Authority type: regulation; as written: LDC Sec. 34-411. - General standards; pincite: 34-411(g), (i).

Cited for: Planned developments must protect natural features and minimize impacts on surroundings

Quotes: ['(g)Every effort shall be made in the planning, design and execution of a planned development to protect, preserve or to not unnecessarily destroy or alter natural, historic or archaeological features of the site...', '(i) Site planning and design shall minimize any negative impacts of the planned development on surrounding land and land uses.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 34-411(g) and (i) quoted verbatim (last amended 2019).

Excerpt read: "(g) Every effort shall be made in the planning, design and execution of a planned development to protect, preserve or to not unnecessarily destroy or alter natural, historic or archaeological features of the site... (i) Site planning and design shall minimize any negative impacts of the planned development on surrounding land and land uses."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 197: Lee County LDC s. 10-321

Document: 1774361815-petition.docx; location: petition.docx.md line 697-699.

Authority type: regulation; as written: Land Development Code, Division 3 – Surface Water Management Sec. 10-321; pincite: 10-321.

Cited for: Surface water plans must mimic natural systems

Quotes: ['Surface water management plans for developments within urban areas must mimic natural systems where feasible', 'techniques to mimic the function of natural systems are specified in Section 10-418.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-321(b)(2) contains the quoted urban-area language and cross-reference to s. 10-418. The subject site is outside the future urban areas, for which (b)(1) applies instead. Section amended by Ord. 25-09 (Apr. 15, 2025), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: "(2) Surface water management plans for developments within urban areas must mimic natural systems where feasible. Techniques to mimic the function of natural systems are specified in Section 10-418."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: UNABLE_TO_VERIFY

The first reviewer read current code text but expressly did not retrieve the pre-amendment version applicable to the cited document. The cited historical requirement remains unverified; the current text and amendment history do not establish its earlier wording. Original first-check explanation: LDC s. 10-321(b)(2) contains the quoted urban-area language and cross-reference to s. 10-418. The subject site is outside the future urban areas, for which (b)(1) applies instead. Section amended by Ord. 25-09 (Apr. 15, 2025), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: "(2) Surface water management plans for developments within urban areas must mimic natural systems where feasible. Techniques to mimic the function of natural systems are specified in Section 10-418."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 198: Lee County LDC s. 10-418

Document: 1774361815-petition.docx; location: petition.docx.md line 699 (within s. 10-321 quotation).

Authority type: regulation; as written: Section 10-418; pincite: 10-418.

Cited for: Techniques to mimic natural systems

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-418 (Surface water management systems; design standards) contains the techniques to mimic natural systems. Section amended by Ord. 25-09 (Apr. 15, 2025), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: "Sec. 10-418. - Surface water management systems. Design standards. Techniques to..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: UNABLE_TO_VERIFY

The first reviewer read current code text but expressly did not retrieve the pre-amendment version applicable to the cited document. The cited historical requirement remains unverified; the current text and amendment history do not establish its earlier wording. Original first-check explanation: LDC s. 10-418 (Surface water management systems; design standards) contains the techniques to mimic natural systems. Section amended by Ord. 25-09 (Apr. 15, 2025), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: "Sec. 10-418. - Surface water management systems. Design standards. Techniques to..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 199: Lee County Code of Ordinances s. 11-480 (labeled LDC)

Document: 1774361815-petition.docx; location: petition.docx.md line 785.

Authority type: regulation; as written: LDC Sec. 11-480; pincite: 11-480.

Cited for: Defines (without limiting) damages and costs from hazardous pollutant incidents

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Section 11-480 is in the Lee County Code of Ordinances (hazardous materials cost recovery), not the LDC. It defines "costs" as including but not limited to response costs and damages to natural resources from a "hazardous materials incident" (Petition: "hazardous pollutant incidents").

Excerpt read: "Costs means and includes, but is not limited to: ... (2) Damages for injury to, destruction of, or loss of natural resources ... resulting from a hazardous materials incident."

- https://library.municode.com/fl/lee_county/codes/code_of_ordinances?nodeId=PTIICOOR_CH11ENNARE

### Second check: not required


## 200: Fla. R. App. P. 9.045

Document: 1774361815-petition.docx; location: petition.docx.md line 887-889 (Certificate of Compliance).

Authority type: court_rule; as written: Fla. R. App. P. 9.045; pincite: 9.045.

Cited for: Font and format requirements

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 9.045 requires computer-generated documents in Arial 14-point or Bookman Old Style 14-point.

Excerpt read: "Computer-generated documents shall be filed in either Arial 14-point font or Bookman Old Style 14-point font."

- https://rules.floridaappellate.com/rule-9-045/

### Second check: not required


## 201: Fla. R. App. P. 9.210

Document: 1774361815-petition.docx; location: petition.docx.md line 887-889 (Certificate of Compliance).

Authority type: court_rule; as written: 9.210; pincite: 9.210.

Cited for: Word count requirements

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Rule 9.210 sets brief length limits (initial briefs 13,000 words); the certificate's statement that the document "does not exceed 30,000 words" does not track the rule's limit, though the rule is the correct source for word limits.

Excerpt read: "(B) ... the initial and answer briefs shall not exceed 13,000 words or 50 pages..."

- https://rules.floridaappellate.com/rule-9-210/

### Second check: not required


## 202: Fla. R. Gen. Prac. & Jud. Admin. 2.520

Document: 1774361815-petition.docx; location: petition.docx.md line 887-889 (Certificate of Compliance).

Authority type: court_rule; as written: Florida Rule of General Practice and Judicial Administration 2.520; pincite: 2.520.

Cited for: Document requirements

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Florida Rule of General Practice and Judicial Administration 2.520 (documents) exists by number, but the Florida Bar rules PDF was not retrievable in this session, so its text was not read.

Excerpt read: Not read (download blocked).

- https://www.floridabar.org/rules/ctproc/

### Second check: not required


## 203: Lee County LDC s. 34-1441 et seq.

Document: 1774361815-resolution.docx; location: resolution Section B.2.a (Schedule of Uses).

Authority type: regulation; as written: LDC S 34-1441 et. seq.; pincite: 34-1441.

Cited for: Wireless communication facility use

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 34-1441 et seq. is the wireless communications facilities division.

Excerpt read: "Sec. 34-1441. - Purpose and intent. ... Promote the health, safety and general welfare of the public by regulating the siting of wireless communications facilities"

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 204: Lee County LDC s. 10-351

Document: 1774361815-resolution.docx; location: resolution Section B.2.b (Setbacks).

Authority type: regulation; as written: In accordance with LDC S 10-351; pincite: 10-351.

Cited for: Wastewater treatment plant setbacks

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-351(d)(2) sets a 100-foot perimeter setback for aboveground treatment facilities, consistent with the setback cross-reference.

Excerpt read: "(2) All aboveground or partially aboveground facilities (active or passive) shall be set back at least 100 feet from any perimeter property line."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: not required


## 205: Lee County LDC s. 34-2173

Document: 1774361815-resolution.docx; location: resolution Section B.2.b (Maximum Height).

Authority type: regulation; as written: LDC S 34-2173; pincite: 34-2173.

Cited for: Structures allowed to 60 feet

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 34-2173 allows listed structural appurtenances to exceed height limits, the cross-reference used for the 60-foot height allowance.

Excerpt read: "Sec. 34-2173. - Exception to height limitations for certain structural elements. (a) The following structural appurtenances may exceed the height limitations..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 206: Lee County LDC s. 10-415(b)(4)

Document: 1774361815-resolution.docx; location: resolution Section B.6.a.ii.

Authority type: regulation; as written: LDC S 10-415(b)4; pincite: 10-415(b)4.

Cited for: Indigenous management plan

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-415(b)(4) requires an indigenous vegetation management plan for indigenous open space.

Excerpt read: "(4) Maintenance. A plan must be submitted for the long-term maintenance of vegetation in indigenous open space areas. This indigenous vegetation management plan must include..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: not required


## 207: Lee County LDC s. 10-416(d)(3)

Document: 1774361815-resolution.docx; location: resolution Section C.1 (Deviation 1).

Authority type: regulation; as written: LDC S 10-416(d)(3); pincite: 10-416(d)(3).

Cited for: 30-foot Type F buffer for wastewater plants abutting public preserve

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The LDC s. 10-416 buffer table requires a Type F buffer where a sewer treatment plant (STP) abuts public preserve land (PRE); Type F minimum width is 30 feet. Section amended by Ord. 24-14 (Oct. 1, 2024), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: Buffer requirements table, row STP / column PRE: "F(2)"; buffer types table: "F ... Minimum width in feet 30"

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: UNABLE_TO_VERIFY

The first reviewer read current code text but expressly did not retrieve the pre-amendment version applicable to the cited document. The cited historical requirement remains unverified; the current text and amendment history do not establish its earlier wording. Original first-check explanation: The LDC s. 10-416 buffer table requires a Type F buffer where a sewer treatment plant (STP) abuts public preserve land (PRE); Type F minimum width is 30 feet. Section amended by Ord. 24-14 (Oct. 1, 2024), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: Buffer requirements table, row STP / column PRE: "F(2)"; buffer types table: "F ... Minimum width in feet 30"

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 208: Lee County LDC s. 10-329(d)(4)

Document: 1774361815-resolution.docx; location: resolution Section C.2 (Deviation 2).

Authority type: regulation; as written: LDC S 10-329(d)(4); pincite: 10-329(d)(4).

Cited for: 6:1 lake bank slope

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-329(d)(4) requires excavation banks sloped no steeper than six horizontal to one vertical. Section amended by Ord. 25-09 (Apr. 15, 2025), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: "(4) Bank slopes. ... The banks of excavations permitted under this section must be sloped at a ratio not greater than six horizontal to one vertical..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: UNABLE_TO_VERIFY

The first reviewer read current code text but expressly did not retrieve the pre-amendment version applicable to the cited document. The cited historical requirement remains unverified; the current text and amendment history do not establish its earlier wording. Original first-check explanation: LDC s. 10-329(d)(4) requires excavation banks sloped no steeper than six horizontal to one vertical. Section amended by Ord. 25-09 (Apr. 15, 2025), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: "(4) Bank slopes. ... The banks of excavations permitted under this section must be sloped at a ratio not greater than six horizontal to one vertical..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 209: Lee County LDC s. 10-418(2)(c)

Document: 1774361815-resolution.docx; location: resolution Section C.3 (Deviation 3).

Authority type: regulation; as written: LDC S 10-41 8(2)(c); pincite: 10-418(2)(c).

Cited for: 20-foot planted littoral shelf

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-418(2)c.1 requires a 20-foot-wide planted littoral shelf no deeper than two feet below control elevation. Section amended by Ord. 25-09 (Apr. 15, 2025), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: "c. Shelf configuration. 1. The PLS must be designed to include a minimum of a 20-foot-wide littoral shelf extending waterward of the control elevation at a depth of no greater than two feet below the control elevation."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: UNABLE_TO_VERIFY

The first reviewer read current code text but expressly did not retrieve the pre-amendment version applicable to the cited document. The cited historical requirement remains unverified; the current text and amendment history do not establish its earlier wording. Original first-check explanation: LDC s. 10-418(2)c.1 requires a 20-foot-wide planted littoral shelf no deeper than two feet below control elevation. Section amended by Ord. 25-09 (Apr. 15, 2025), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: "c. Shelf configuration. 1. The PLS must be designed to include a minimum of a 20-foot-wide littoral shelf extending waterward of the control elevation at a depth of no greater than two feet below the control elevation."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 210: Lee County LDC s. 10-291(3)

Document: 1774361815-resolution.docx; location: resolution Section C.4 (Deviation 4).

Authority type: regulation; as written: LDC S 10-291 (3); pincite: 10-291(3).

Cited for: Commercial/industrial development over ten acres needs two access points

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-291(3) requires commercial or industrial development over ten acres to provide more than one means of ingress or egress. Section amended by Ord. 25-09 (Apr. 15, 2025), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: "(3) Residential development of more than five acres and commercial or industrial development of more than ten acres must provide more than one means of ingress or egress for the development."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: UNABLE_TO_VERIFY

The first reviewer read current code text but expressly did not retrieve the pre-amendment version applicable to the cited document. The cited historical requirement remains unverified; the current text and amendment history do not establish its earlier wording. Original first-check explanation: LDC s. 10-291(3) requires commercial or industrial development over ten acres to provide more than one means of ingress or egress. Section amended by Ord. 25-09 (Apr. 15, 2025), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: "(3) Residential development of more than five acres and commercial or industrial development of more than ten acres must provide more than one means of ingress or egress for the development."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 211: Lee Plan (Lee County Comprehensive Plan) goals, objectives, policies, standards and maps

Document: 1774361815-resolution.docx; location: resolution Section E.1.a.

Authority type: other; as written: Lee Plan Goals 2, 4, 33, 56, 77, 1 15, 124, 125, Objectives 1.5, 2.1, 2.2, 125.1, 158.3, and Policies 1 .1.8, 2.2.1 , 5.1 .5, 33.1.7, 56.1 .3, 60.1.1, 60.1 .2, 123.2.3, 125.1.2, 125.1.3. 126.1.1, Standards 4.1.1, 4.1.2, 4.1.4; Lee Plan Maps IA-B, 4B; pincite: .

Cited for: CFPD complies with the Lee Plan

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The Lee Plan goal, objective, policy and map numbers listed in the resolution's findings were not checked individually against the Lee Plan in effect in January 2024; existence and support are unverified.

Excerpt read: Not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx

### Second check: not required


## 212: Lee County LDC chapters 10 and 34

Document: 1774361815-resolution.docx; location: resolution Section E.1.b.

Authority type: regulation; as written: LDC Chapters 10 and 34; pincite: .

Cited for: Complies with LDC or qualifies for deviations

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC chapters 10 (Development Standards) and 34 (Zoning) exist and contain the cited regulations.

Excerpt read: Chapter 10 - DEVELOPMENT STANDARDS; Chapter 34 - ZONING

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 213: Lee Plan Policies 1.1.8, 2.1.1, 2.1.2, 2.2.1

Document: 1774361815-resolution.docx; location: resolution Section E.1.c.

Authority type: other; as written: Lee Plan Policies 1.1 .8, 2.1.1, 2.1 .2, 2.2.1; pincite: .

Cited for: Compatible with existing and planned uses

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The Lee Plan goal, objective, policy and map numbers listed in the resolution's findings were not checked individually against the Lee Plan in effect in January 2024; existence and support are unverified.

Excerpt read: Not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx

### Second check: not required


## 214: Lee County LDC s. 34-411(c), (i), (j)

Document: 1774361815-resolution.docx; location: resolution Section E.1.c.

Authority type: regulation; as written: LDC 34-41 1(c), (i), and (j); pincite: 34-411(c), (i), (j).

Cited for: Compatible with existing and planned uses

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 34-411(c), (i) and (j) address location to minimize negative effects on surrounding properties, minimizing impacts on surrounding land, and integration with compatible surroundings, supporting the compatibility finding.

Excerpt read: "(c) The tract or parcel ... must be located so as to minimize the negative effects of the resulting land uses on surrounding properties..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 215: Lee Plan Policies 37.3.3, 39.1.1

Document: 1774361815-resolution.docx; location: resolution Section E.1.d.

Authority type: other; as written: Lee Plan Policy 37.3.3, 39.1.1; pincite: .

Cited for: Sufficient access; transportation impacts addressed

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The Lee Plan goal, objective, policy and map numbers listed in the resolution's findings were not checked individually against the Lee Plan in effect in January 2024; existence and support are unverified.

Excerpt read: Not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx

### Second check: not required


## 216: Lee Plan Goals 77, 124, 125, Objectives 1.5, 4.1, 77.1, Policies 124.1.2, 125.1.2, 125.1.3, Standard 4.1.4

Document: 1774361815-resolution.docx; location: resolution Section E.1.e (finding text partly in inline images).

Authority type: other; as written: Lee Plan Goals 77, 124, 125, Objectives 1.5, 4.1, 77.1, Policy 124.1 .2, 125.1.2, 125.1 .3, Standard 4.1.4; pincite: .

Cited for: No adverse effect on environmentally critical areas

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The Lee Plan goal, objective, policy and map numbers listed in the resolution's findings were not checked individually against the Lee Plan in effect in January 2024; existence and support are unverified.

Excerpt read: Not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx

### Second check: not required


## 217: Lee County LDC s. 34-411(h)

Document: 1774361815-resolution.docx; location: resolution Section E.1.e (subsection letter in inline image).

Authority type: regulation; as written: LDC S 34-41 1(h).; pincite: 34-411(h).

Cited for: No adverse effect on environmentally critical areas

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 34-411(h) ties planned-development open space to preservation or conservation of environmentally sensitive land and waters, consistent with the environmental finding.

Excerpt read: "(h) ... This shall be coordinated with the achievement of other goals, e.g., the preservation or conservation of environmentally sensitive land and waters or archaeological sites."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 218: Lee Plan Glossary, Map 4A-B, Goal 2; Objectives 2.1, 2.2, 4.1, 53.1, 56.1; Policy 2.2.1; Standards 4.1.1, 4.1.2

Document: 1774361815-resolution.docx; location: resolution Section E.1.f.

Authority type: other; as written: Lee Plan Glossary, Map 4A-B, Goal 2; Objectives 2.1, 2.2, 4.1 , 53.1 , 56.1; Policies 2.2.1, and Standards 4.1.1 and 4.1.2; pincite: .

Cited for: Served by urban services

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The Lee Plan goal, objective, policy and map numbers listed in the resolution's findings were not checked individually against the Lee Plan in effect in January 2024; existence and support are unverified.

Excerpt read: Not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx

### Second check: not required


## 219: Lee County LDC s. 34-411(d)

Document: 1774361815-resolution.docx; location: resolution Section E.1.f.

Authority type: regulation; as written: LDC S 34-41 1 (d); pincite: 34-411(d).

Cited for: Served by urban services

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

LDC s. 34-411(d) concerns road access, not service by urban services; cited loosely for the urban-services finding.

Excerpt read: "(d) All planned developments must have access to existing or proposed roads..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 220: Lee Plan Goal 39, Objective 39.1

Document: 1774361815-resolution.docx; location: resolution Section E.2.

Authority type: other; as written: Lee Plan Goal 39, Objective 39.1; pincite: .

Cited for: MCP reflects sufficient access

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The Lee Plan goal, objective, policy and map numbers listed in the resolution's findings were not checked individually against the Lee Plan in effect in January 2024; existence and support are unverified.

Excerpt read: Not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx

### Second check: not required


## 221: Lee County LDC s. 34-411(d)

Document: 1774361815-resolution.docx; location: resolution Section E.2.

Authority type: regulation; as written: LDC S 34-41 1 (d); pincite: 34-411(d).

Cited for: MCP reflects sufficient access

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 34-411(d) requires planned developments to have access to existing or proposed roads.

Excerpt read: "(d) All planned developments must have access to existing or proposed roads. Access must comply with the requirements of Chapter 10..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 222: Lee Plan Policies 1.1.8, 2.1.1

Document: 1774361815-resolution.docx; location: resolution Section E.3.

Authority type: other; as written: Lee Policies 1.1.8, 2. 1 . 1; pincite: .

Cited for: Mix of uses appropriate at location

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The Lee Plan goal, objective, policy and map numbers listed in the resolution's findings were not checked individually against the Lee Plan in effect in January 2024; existence and support are unverified.

Excerpt read: Not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx

### Second check: not required


## 223: Lee County LDC chapters 10 and 34

Document: 1774361815-resolution.docx; location: resolution Section E.4.

Authority type: regulation; as written: LDC Chapters 10 and 34; pincite: .

Cited for: Conditions sufficient to protect public interest

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC chapters 10 (Development Standards) and 34 (Zoning) exist and contain the cited regulations.

Excerpt read: Chapter 10 - DEVELOPMENT STANDARDS; Chapter 34 - ZONING

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST
- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO

### Second check: not required


## 224: Lee County LDC s. 34-377(a)(4)

Document: 1774361815-resolution.docx; location: resolution Section E.5 (pin cite in inline image).

Authority type: regulation; as written: LDC S 34-377( [truncated in image]; pincite: 34-377(.

Cited for: Deviations enhance PD objectives and promote LDC intent

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The pin cite is cut off in the resolution (an inline image reads "34-377("). LDC s. 34-377(a)(4) contains the two deviation findings the resolution recites.

Excerpt read: s.34-377(a)(4): "...each item: a. Enhances the achievement of the objectives of the planned development; and b. Preserves and promotes the general intent of this chapter to protect the public health, safety and welfare."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH34ZO
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx

### Second check: not required


## 225: Fla. Admin. Code ch. 5J-17

Document: 1774361815-resolution.docx; location: resolution Exhibit A, sketch sheet 1 (surveyor certification).

Authority type: regulation; as written: CHAPTER 50-17.05 [5J-17.05], FLORIDA ADMINISTRATIVE CODE; pincite: .

Cited for: Sketch prepared under surveying standards of practice

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Chapter 5J-17, F.A.C. (Professional Surveyors and Mappers) exists, but standards of practice are now numbered 5J-17.050-.053; "5J-17.05" is an older rule number. The converted text garbles it as "50-17.05".

Excerpt read: "5J-17.050 Definitions ... 5J-17.051 Standards of Practice - General Survey, MAP, and Report Content Requirements ... 5J-17.052 Standards of Practice - Boundary Survey Requirements"

- https://www.flrules.org/gateway/ChapterHome.asp?Chapter=5J-17

### Second check: not required


## 226: Fla. Stat. ch. 472

Document: 1774361815-resolution.docx; location: resolution Exhibit A, sketch sheet 1 (surveyor certification).

Authority type: statute; as written: CHAPTER 472, FLORIDA STATUTES; pincite: .

Cited for: Surveying statute

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter 472 (Land Surveying and Mapping) is the surveyor licensing chapter the certification invokes.

Excerpt read: "Chapter 472 LAND SURVEYING AND MAPPING"

- http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&StatuteYear=2024&URL=0400-0499/0472/0472ContentsIndex.html

### Second check: not required


## 227: Lee County LDC s. 10-261

Document: 1774361815-resolution.docx; location: resolution Exhibit C, Master Concept Plan note 9.

Authority type: regulation; as written: LDC SECTION 10-261; pincite: 10-261.

Cited for: On-site solid waste disposal area

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-261 governs refuse and solid waste disposal facilities. Section amended by Ord. 24-14 (Oct. 1, 2024) and Ord. 26-07 (June 16, 2026), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: "Sec. 10-261. - Refuse and solid waste disposal facilities. (a) Provision of container spaces..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: UNABLE_TO_VERIFY

The first reviewer read current code text but expressly did not retrieve the pre-amendment version applicable to the cited document. The cited historical requirement remains unverified; the current text and amendment history do not establish its earlier wording. Original first-check explanation: LDC s. 10-261 governs refuse and solid waste disposal facilities. Section amended by Ord. 24-14 (Oct. 1, 2024) and Ord. 26-07 (June 16, 2026), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: "Sec. 10-261. - Refuse and solid waste disposal facilities. (a) Provision of container spaces..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 228: Lee County LDC s. 10-261

Document: 1774361815-resolution.docx; location: resolution Exhibit C, Master Concept Plan note 9 (second MCP sheet).

Authority type: regulation; as written: LDC SECTION 10-261; pincite: 10-261.

Cited for: On-site solid waste disposal area

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

LDC s. 10-261 governs refuse and solid waste disposal facilities. Section amended by Ord. 24-14 (Oct. 1, 2024) and Ord. 26-07 (June 16, 2026), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: "Sec. 10-261. - Refuse and solid waste disposal facilities. (a) Provision of container spaces..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

### Second check: UNABLE_TO_VERIFY

The first reviewer read current code text but expressly did not retrieve the pre-amendment version applicable to the cited document. The cited historical requirement remains unverified; the current text and amendment history do not establish its earlier wording. Original first-check explanation: LDC s. 10-261 governs refuse and solid waste disposal facilities. Section amended by Ord. 24-14 (Oct. 1, 2024) and Ord. 26-07 (June 16, 2026), after the document; the pre-amendment text was not retrieved. The cited requirement is in the current text.

Excerpt read: Integration reviewed the saved first-check excerpt and coverage statement; no additional primary authority text was read. Saved excerpt: "Sec. 10-261. - Refuse and solid waste disposal facilities. (a) Provision of container spaces..."

- https://library.municode.com/fl/lee_county/codes/land_development_code?nodeId=LADECO_CH10DEST

Model: GPT-6.1 Sol integration coverage review; reasoning effort: medium.

## 230: 14 CFR Part 150, Airport Noise Compatibility Planning

Document: 1774361815-petition.docx; location: petition.docx.md line 557 (standalone Southwest Florida International Airport study reference).

Authority type: regulation; as written: Southwest Florida International Airport 14 CFR Part 150 Study; pincite: Part 150.

Cited for: Identifies the regulatory basis of an airport noise-compatibility study

Quotes: []

Context: The Petition lists the study separately from its three block quotations of LDC 34-1102.

Fictional by design: False; 

### First check: VERIFIED

Part 150 is a real FAA regulation governing airport noise exposure maps and compatibility programs. The sentence cites a particular airport study, whose actual contents were not supplied or independently checked; only the regulatory identity is verified.

Excerpt read: Part 150 is headed Airport Noise Compatibility Planning; section 150.1 covers noise exposure maps and compatibility programs.

- https://www.ecfr.gov/current/title-14/chapter-I/subchapter-I/part-150

### Second check: not required
