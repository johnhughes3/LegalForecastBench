# Citation checks: lrb-forum-non-conveniens-response

AI-generated citation checks, not human legal verification or score corrections. The counting unit is a citation in a unique matter document, not each repeated assignment packet. Worker file lists and limits are reproduced below; absence of a stated limit does not independently establish exhaustive coverage. Completion requires an explicit census-complete judgment; verification limits remain visible. Every first-check problem requires an independent second check, including overturned findings. Missing files and pending checks never establish a zero-problem result.

Model: Claude Opus 5.5; reasoning effort: high.

Worker coverage: {'files_read': ['https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/instruction.md', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/tests/fixtures/rubric.json', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-2/instruction.md', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-2/tests/fixtures/rubric.json', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Defendants%20Motion%20to%20Transfer.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Davis%20Complaint.docx', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf'], 'limits': ["Attachment counting: the six attachments are identical in assignment-1 and assignment-2 packets apart from the source-URL line (verified by diff); each is counted once. Prompts and rubric fields are counted per assignment; assignment-2's copy of the prior assignment-1 prompt contains no citations.", "All text read is the repository's extraction of the pinned upstream files (no OCR). No attachment page was marked as lacking extracted text. The 303-page 2023 Annual Report is mostly numeric tables; 16 near-empty pages are section dividers or charts with little text, and chart/table layouts in the extraction scramble some row/column labels (affects one motion citation marked UNABLE_TO_VERIFY).", 'The Davis Complaint is a DOCX conversion; original pagination is not retained, so complaint locations are by paragraph.', "The Langenhorst attachment runs from the majority's 'Affirmed.' directly into Justice Garman's dissent (PDF pp.12-20) without a dissent heading; dissent locations are labelled in this file.", "Pin-cite checks for Illinois Reports pages rely on page markers in CourtListener's Harvard CAP text (mapped with a constant per-opinion offset confirmed against several known pins); where no markers were available the proposition, not the page, was checked.", 'Statutes and Supreme Court Rules were read in their current official versions (ILGA, illinoiscourts.gov compiled rules current to Oct. 16, 2026). Historical editions cited in the opinions (e.g. West 1992/2000, 134 Ill. 2d Rules) were not read; where numbering changed (Rule 306) this is flagged.', "The 2023 Annual Report attachment was checked only against itself (it is the cited document); it was not compared with the AOIC's published PDF.", "The assignment-1 prompt contains an uncited legal assertion (venue in wrongful death proper where any part of the action occurred, including the place of death); with no authority named or quoted it is not counted. The assignment-2 prompt's sentence is counted because it quotes Langenhorst's language verbatim.", 'Embedded pin cites to Dawdy (76) and Guerine (44) inside Langenhorst were checked by reading those opinions with Illinois Reports page markers; each record carries a page-specific excerpt.', "Embedded citations in the three supplied opinions were checked for identity via CourtListener citation lookup and, for propositions, by reading the cited passage on CourtListener; supplied opinion texts were themselves compared with CourtListener's official text at sampled passages (matching).", "No upstream scripts were run, and no paid APIs were used. CourtListener was reached through its connector. ILGA pages were fetched directly; the site's TLS chain needed the published Sectigo intermediate certificate, and verification was not disabled.", "The original exclusion of bare case-name references was corrected by a complete supplemental scan of readable text. It adds 97 named-authority short forms, all checked against judicial text; the first second-review worker's eleven additions are included exactly once. Primary-source access and extraction limits remain as stated.", 'Counting includes named-authority short forms after the supplemental census; the initial bare-name exclusion is superseded. Repeated attachment copies and non-authority record references are excluded.', 'All 63 initially unverified occurrences received retrieval attempts. Independent review retained the Ferris wrong-citation claim and treated five challenged supervisory-order parentheticals as minor defects; all nine supplemental proposals have saved second judgments and rubric-intent records.', 'Remaining unverified occurrences concern Restatement section 84 comment c, the Maag/Kitch/Sunderland articles, historical Rule 306, and the truncated Lawson and Eby supervisory orders. The per-reference attempts specify what was unavailable. Historical rule versions beyond those actually read remain a limit.', 'Current recorded coverage: 663 real-authority occurrences, including 10 UNABLE_TO_VERIFY. Status totals are derived from the saved per-reference judgments; historical aggregate statements above do not control current counts.'], 'counting_unit': 'citation occurrence in each unique matter document, separate prompt and rubric occurrences', 'counts': {'total_occurrences': 573, 'real_law': 566, 'fictional_by_design': 7, 'first_check_status': {'VERIFIED': 459, 'VERIFIED_MINOR_DEFECT': 27, 'MISCHARACTERIZED': 17, 'UNABLE_TO_VERIFY': 63}, 'problems': 17}, 'census_complete': True}

## FNC-0001: Davis v. Smith (scenario case)

Document: assignment-1 prompt (instruction.md / input.json "prompt"); location: assignment-1 prompt, memo heading "Re: Davis v. Smith".

Authority type: case; as written: Davis v. Smith; pincite: .

Cited for: Scenario matter caption

Quotes: []

Context: 

Fictional by design: True; Fictional scenario lawsuit (Davis v. Smith, Cook County) created for the task.

### First check: excluded by design


### Second check: not required


## FNC-0002: Davis v. Smith (scenario case)

Document: assignment-2 prompt (instruction.md / input.json "prompt"); location: assignment-2 prompt, memo heading "Re: Davis v. Smith".

Authority type: case; as written: Davis v. Smith; pincite: .

Cited for: Scenario matter caption

Quotes: []

Context: 

Fictional by design: True; Fictional scenario lawsuit (Davis v. Smith, Cook County) created for the task.

### First check: excluded by design


### Second check: not required


## FNC-0003: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 prompt (instruction.md / input.json "prompt"); location: assignment-2 prompt, paragraph 1.

Authority type: case; as written: "the burden is on the defendants to show that relevant private and public interest factors “strongly favor” the defendant's choice of forum to warrant disturbing plaintiff's choice" (uncited quotation); pincite: .

Cited for: Defendants bear the burden to show the factors strongly favor their forum

Quotes: ["the burden is on the defendants to show that relevant private and public interest factors “strongly favor” the defendant's choice of forum to warrant disturbing plaintiff's choice"]

Context: Assignment-2 memo characterizes the best argument for the response brief.

Fictional by design: False; 

### First check: VERIFIED

Uncited paraphrase/quotation of Langenhorst; the sentence appears in the supplied Langenhorst opinion (attachment PDF p.7) citing Griffith, 136 Ill. 2d at 107, and in the official text on CourtListener.

Excerpt read: Langenhorst (attachment p.7; CourtListener 9819147): 'The burden is on the defendant to show that relevant private and public interest factors "strongly favor" the defendant's choice of forum to warrant disturbing plaintiff's choice.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0004: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_1 (required, +3 pts), "criterion" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995); pincite: .

Cited for: Bradbury motion was not supported by affidavits (contrast with defendants' two affidavits here)

Quotes: []

Context: States in Assignment #1that the Defendants motion was supported by two affidavits which was absent in Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995).

Fictional by design: False; 

### First check: VERIFIED

Bradbury (attachment p.3) states the FNC motion 'was not verified and it was not supported by any affidavits.' Citation (273 Ill. App. 3d 555, 1st Dist. 1995) confirmed on CourtListener.

Excerpt read: Supplied Bradbury opinion PDF p.3: 'The defendants' forum non conveniens motion was not verified and it was not supported by any affidavits.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0005: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_1 (required, +3 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary's Hospital.pdf at p.3); pincite: p.3.

Cited for: same

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary’s Hospital.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the passage.

Excerpt read: Supplied Bradbury opinion PDF p.3: 'The defendants' forum non conveniens motion was not verified and it was not supported by any affidavits.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0006: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_2 (required, +5 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Defendant's affidavit must show the plaintiff's chosen forum (Cook) is inconvenient to the defendant

Quotes: []

Context: Identifies in Assignment #1 an affidavit by John Smith, M.D. does not indicate that Cook County would be an inconvenient forum for him to litigate this case as required under Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: VERIFIED

Langenhorst p.3 notes the defendants' affidavits said Clinton County was not inconvenient but 'did not indicate these defendants would be inconvenienced by appearing at a trial in St. Clair County', and p.10 restates that the defendant must show the chosen forum is inconvenient to the defendant. The criterion's framing (Smith affidavit says DuPage more convenient, not that Cook is inconvenient) tracks that reasoning.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0007: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_2 (required, +5 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006) (Langenhorst v. Norfolk Southern.pdf at p.10); pincite: p.10.

Cited for: same

Quotes: []

Context: Defendants Motion to Transfer.pdf (Defendants Motion to Transfer.pdf at p.8) stating "Trial of this matter in the Circuit Court of DuPage County would be substantially more convenient for me, both as a party and as a fact witness, than trial in the Circuit Court of Cook County." and Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006) (Langenhorst v. Norfolk Southern.pdf at p.10).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the affidavit discussion and the defendant-must-show rule.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0008: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_3 (required, +5 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Hospital affidavit must show Cook is inconvenient to it

Quotes: []

Context: Identifies in Assignment #1 an affidavit by Safe Hospital representative does not indicate that Cook County would be an inconvenient forum for them to litigate this case as required under Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: VERIFIED

Same Langenhorst reasoning as criterion_2 (pp.3, 10).

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0009: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_3 (required, +5 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006) (Langenhorst v. Norfolk Southern.pdf at p.10); pincite: p.10.

Cited for: same

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006) (Langenhorst v. Norfolk Southern.pdf at p.10).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the passage.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0010: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_4 (required, +1 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Movant bears burden to show private interest factors with all others strongly favor its forum

Quotes: []

Context: States in Assignment #1 that the burden is on the movant to show that the balance of private interest factors with all other factors, strongly favors the proposed forum, under Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: VERIFIED

Langenhorst p.7 states the burden and the total-circumstances rule.

Excerpt read: Supplied Langenhorst opinion PDF p.7: 'The burden is on the defendant to show that relevant private and public interest factors "strongly favor" the defendant's choice of forum to warrant disturbing plaintiff's choice.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0011: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_4 (required, +1 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.7); pincite: p.7.

Cited for: same

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.7).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the passage.

Excerpt read: Supplied Langenhorst opinion PDF p.7: 'The burden is on the defendant to show that relevant private and public interest factors "strongly favor" the defendant's choice of forum to warrant disturbing plaintiff's choice.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0012: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_30 (required, +1 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Movant bears burden to show public interest factors with all others strongly favor its forum

Quotes: []

Context: States in Assignment #1 that the burden is on the movant to show that the balance of public interest factors with all other factors, strongly favors the proposed forum under Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: VERIFIED

Langenhorst p.7 states the burden and the total-circumstances rule.

Excerpt read: Supplied Langenhorst opinion PDF p.7: 'The burden is on the defendant to show that relevant private and public interest factors "strongly favor" the defendant's choice of forum to warrant disturbing plaintiff's choice.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0013: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_30 (required, +1 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.7); pincite: p.7.

Cited for: same

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.7).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the passage.

Excerpt read: Supplied Langenhorst opinion PDF p.7: 'The burden is on the defendant to show that relevant private and public interest factors "strongly favor" the defendant's choice of forum to warrant disturbing plaintiff's choice.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0014: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_5 (required, +3 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Plaintiff's forum choice gets less deference when plaintiff resides outside the forum

Quotes: []

Context: Mentions in Assignment #1 that the plaintiff’s interest in choosing the forum receives less deference when the plaintiff’s residence is located outside the chosen forum, under Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Langenhorst (p.6, p.9) supports reduced deference, but its rule is conjunctive: 'somewhat less deference when neither the plaintiff's residence nor the site of the accident or injury is located in the chosen forum.' The criterion drops the accident/injury-site condition, which matters here because the decedent died in Cook County.

Excerpt read: Supplied Langenhorst opinion PDF p.6: 'the plaintiff's interest in choosing the forum receives "somewhat less deference when neither the plaintiff's residence nor the site of the accident or injury is located in the chosen forum."'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0015: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_5 (required, +3 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.7); pincite: p.7.

Cited for: same

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.7).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The reduced-deference passages are at attachment pp.6 and 9, not p.7; the paraphrase also omits the accident/injury-site condition.

Excerpt read: Supplied Langenhorst opinion PDF p.6: 'somewhat less deference when neither the plaintiff's residence nor the site of the accident or injury is located in the chosen forum.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0016: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_6 (required, +3 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Reviewing court affirmed denial of transfer though plaintiff resided outside the chosen forum

Quotes: []

Context: Identifies in Assignment #1 that in Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006) the reviewing court affirmed the denial of transfer even though the plaintiff’s residence was outside the chosen forum.

Fictional by design: False; 

### First check: VERIFIED

Plaintiff resided in Clinton County and sued in St. Clair County; the supreme court affirmed the denial of transfer.

Excerpt read: Supplied Langenhorst opinion PDF p.12: 'Accordingly, we hold that the circuit court did not abuse its discretion in denying defendants' motion to transfer this cause to Clinton County ... we affirm the judgment of the appellate court.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0017: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_6 (required, +3 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.12); pincite: p.12.

Cited for: same

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.12).

Fictional by design: False; 

### First check: VERIFIED

Disposition is on p.12.

Excerpt read: Supplied Langenhorst opinion PDF p.12: 'For the foregoing reasons, we affirm the judgment of the appellate court.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0018: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_7 (required, +3 pts), "criterion" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555; pincite: .

Cited for: Reviewing court affirmed denial of transfer though plaintiff's residence was not established

Quotes: []

Context: Identifies in Assignment #1 that in Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 the reviewing court affirmed the denial of transfer even though the plaintiff failed to establish residency in the chosen forum.

Fictional by design: False; 

### First check: VERIFIED

Bradbury (pp.4-5) affirmed the denial; the record did not establish residence of plaintiff or decedent.

Excerpt read: Supplied Bradbury opinion PDF p.5: 'The plaintiff's complaint is silent as to her county of residence or that of the decedent ... Accordingly, we affirm the order of the circuit court denying the defendants' motion'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0019: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_7 (required, +3 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary's Hospital.pdf at p.5); pincite: p.5.

Cited for: same

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary’s Hospital.pdf at p.5).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the passage.

Excerpt read: Supplied Bradbury opinion PDF p.5: 'we affirm the order of the circuit court denying the defendants' motion to transfer this action under the doctrine of forum non conveniens'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0020: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_8 (required, +3 pts), "criterion" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002); pincite: .

Cited for: Supreme court reversed a grant of transfer though plaintiffs resided outside the chosen forum

Quotes: []

Context: Identifies in Assignment #1 that in First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) the reviewing court reversed a grant of transfer even though the plaintiff’s residence was outside the chosen forum.

Fictional by design: False; 

### First check: VERIFIED

Plaintiffs lived in Kane County and sued in Cook County; the trial court granted transfer and the supreme court reversed.

Excerpt read: Supplied Guerine opinion PDF p.8: 'For the reasons we have discussed, we reverse the decision of the trial court transferring this cause to Kane County and remand for further proceedings.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0021: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_8 (required, +3 pts), "source" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.10); pincite: p.10.

Cited for: same

Quotes: []

Context: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.10).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Attachment p.10 is the end of the appendix of supervisory orders; the reversal is stated at pp.2 and 8.

Excerpt read: Supplied Guerine opinion PDF p.8: 'we reverse the decision of the trial court transferring this cause to Kane County'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0022: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_10 (required, +10 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary's Hospital.pdf at p.5); pincite: p.5.

Cited for: Plaintiff should file an affidavit establishing residence

Quotes: []

Context: "Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary’s Hospital.pdf at p.5) and First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.7).

Fictional by design: False; 

### First check: VERIFIED

Bradbury p.5 faults the absence of record evidence of residence, supporting the value of a residence affidavit.

Excerpt read: Supplied Bradbury opinion PDF p.5: 'we find no evidentiary support for either statement in the record before us. The plaintiff's complaint is silent as to her county of residence or that of the decedent'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0023: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_10 (required, +10 pts), "source" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.7); pincite: p.7.

Cited for: Plaintiff should file an affidavit establishing residence

Quotes: []

Context: "Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary’s Hospital.pdf at p.5) and First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.7).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Guerine p.7 describes plaintiffs' affidavits, but they addressed convenience ('they will suffer no inconvenience by traveling to Cook County'), not residence; residence came from interrogatory answers (p.1). Loose support for the residence-affidavit point.

Excerpt read: Supplied Guerine opinion PDF p.7: 'the record contains affidavits from Patrick, Christopher, and Samuel Malone stating that they will suffer no inconvenience by traveling to Cook County to litigate this case.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0024: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_11 (required, +15 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10); pincite: p.10.

Cited for: Plaintiff should file an affidavit that litigating in DuPage would be inconvenient

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Langenhorst p.10 discusses the absence of affidavits that the CHOSEN forum was inconvenient and restates that the defendant must show another forum is 'more convenient to all parties'. A plaintiff's DuPage-inconvenience affidavit rebuts that prong, so the cite gives indirect support; Langenhorst does not discuss plaintiff-side affidavits.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0025: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_17 (required, +5 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary's Hospital.pdf at p.3); pincite: p.3.

Cited for: Defendants gave no evidentiary basis on compulsory process burden

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary’s Hospital.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Bradbury p.3 describes the unsupported motion; the compulsory-process discussion (Rule 237; failure to identify nonparty witnesses) is on p.4.

Excerpt read: Supplied Bradbury opinion PDF p.4: 'process would be available in either county to compel the attendance of any unwilling Illinois resident witnesses pursuant to Supreme Court Rule 237 ... they have failed to identify any nonparty witnesses from Kankakee County.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0026: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_18 (required, +5 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: "We live in a smaller world" ... convenience has a different meaning

Quotes: []

Context: Mentions in Assignment #1 that we live in a smaller world, we are connected by interstate highways, bustling airways, today, convenience - the touchstone of the forum non conveniens doctrine has a different meaning, under Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: VERIFIED

Langenhorst p.10 quotes Guerine's 'smaller world' passage.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'As this court noted in Guerine, "We live in a smaller world * * *. Today, we are connected by interstate highways, bustling airways, telecommunications, and the world wide web. Today, convenience-the touchstone of the forum non conveniens doctrine-has a different meaning."'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0027: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_18 (required, +5 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10); pincite: p.10.

Cited for: same

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the passage.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'We live in a smaller world * * *.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0028: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_19 (required, +1 pts), "criterion" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002); pincite: .

Cited for: Defendants distinguished Guerine, where witnesses resided in multiple counties

Quotes: []

Context: Identifies in Assignment #1 that the Defendants have distinguished First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) where potential witnesses resided in multiple counties.

Fictional by design: False; 

### First check: VERIFIED

Guerine (pp.7-8) involved witnesses in Cook, De Kalb, Kane, Du Page and Winnebago Counties.

Excerpt read: Supplied Guerine opinion PDF p.7: 'Guerine's passenger McKinney lives in Cook County. Guerine's other passenger Tischer lives in Du Page County, and Baker ... lives in De Kalb County.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0029: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_19 (required, +1 pts), "source" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.7); pincite: p.7.

Cited for: same

Quotes: []

Context: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.7) and Defendants Motion to Transfer.pdf (Defendants Motion to Transfer.pdf at pp.7-8).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the witness-location discussion.

Excerpt read: Supplied Guerine opinion PDF p.7: 'Unlike Torres, but like Hinshaw, the case before us involves parties and witnesses dispersed among several counties in the same area of the state.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0030: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_20 (required, +1 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Defendants distinguished Langenhorst, where witnesses resided in multiple counties

Quotes: []

Context: Identifies in Assignment #1 that the Defendants have distinguished Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006) where potential witnesses resided in multiple counties

Fictional by design: False; 

### First check: VERIFIED

Langenhorst majority (pp.8-11) found witnesses scattered among several counties, Indiana and Missouri.

Excerpt read: Supplied Langenhorst opinion PDF p.8: 'both St. Clair County and Clinton County have significant ties to the case and the potential witnesses are scattered throughout several counties in the state, as well as Indiana and Missouri.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0031: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_20 (required, +1 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.13); pincite: p.13.

Cited for: same

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.13) and and Defendants Motion to Transfer.pdf (Defendants Motion to Transfer.pdf at pp.7-8).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Attachment p.13 is Justice Garman's dissent summarizing Dawdy; the majority's discussion of scattered witnesses is at pp.8-11.

Excerpt read: Supplied Langenhorst opinion PDF p.8: 'the potential witnesses are scattered throughout several counties in the state, as well as Indiana and Missouri.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0032: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_21 (required, +5 pts), "criterion" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995); pincite: .

Cited for: Cook County has an interest because the decedent died there

Quotes: []

Context: States in Assignment #1 that Cook County has an interest in this litigation because the decedent died in Cook County, under Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995).

Fictional by design: False; 

### First check: VERIFIED

Bradbury p.4 so holds.

Excerpt read: Supplied Bradbury opinion PDF p.4: 'Kankakee County has an interest because the action involves alleged acts of medical negligence occurring within its borders, and Cook County has an interest because the decedent died here.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0033: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_21 (required, +5 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Marys Hospital.pdf, p.4); pincite: p.4.

Cited for: same

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Marys Hospital.pdf, p.4).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the passage.

Excerpt read: Supplied Bradbury opinion PDF p.4: 'Cook County has an interest because the decedent died here.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0034: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_22 (penalty, -30 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Marys Hospital.pdf, p.4); pincite: p.4.

Cited for: Authority contradicting the penalized statement that Cook lacks an interest

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Marys Hospital.pdf, p.4).

Fictional by design: False; 

### First check: VERIFIED

Penalty criterion; Bradbury p.4 supports the rubric's position that Cook County has an interest where the decedent died there.

Excerpt read: Supplied Bradbury opinion PDF p.4: 'Because neither county can be said to be totally unrelated to this action, we are unprepared to say that it would be unfair to burden the citizens of either county'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0035: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_23 (required, +5 pts), "criterion" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995); pincite: .

Cited for: Bradbury treated location of death alone as sufficient for Cook County interest

Quotes: []

Context: Identifies in Assignment #1 that Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) treated the location of death alone as sufficient to give Cook County a genuine interest in the litigation.

Fictional by design: False; 

### First check: VERIFIED

Bradbury p.4 gives the decedent's death in Cook County as the sole stated reason for Cook County's interest ('genuine' is the rubric's word).

Excerpt read: Supplied Bradbury opinion PDF p.4: 'Cook County has an interest because the decedent died here.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0036: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_23 (required, +5 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Marys Hospital.pdf, p.4); pincite: p.4.

Cited for: same

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Marys Hospital.pdf, p.4).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the passage.

Excerpt read: Supplied Bradbury opinion PDF p.4: 'Cook County has an interest because the decedent died here.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0037: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_24 (required, +3 pts), "criterion" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002); pincite: .

Cited for: Court congestion is relatively insignificant absent proof the other forum is faster

Quotes: []

Context: States in Assignment #1 that court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly, under First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002).

Fictional by design: False; 

### First check: VERIFIED

Guerine p.3 states the rule verbatim.

Excerpt read: Supplied Guerine opinion PDF p.3: 'Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0038: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_24 (required, +3 pts), "source" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.3); pincite: p.3.

Cited for: same

Quotes: []

Context: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the passage.

Excerpt read: Supplied Guerine opinion PDF p.3: 'Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0039: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_25 (penalty, -30 pts), "source" field.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf at p.21.; pincite: p.21.

Cited for: Cook County overall clearance rate 60.5% (penalized as not the civil figure)

Quotes: []

Context: 2023 Annual Report Statistical Summary.pdf at p.21.

Fictional by design: False; 

### First check: VERIFIED

Report p.21 ('2023 Clearance Rates: All Case Types') shows Cook County 60.5%; the justification correctly notes this is the all-case-types figure, not civil.

Excerpt read: Report p.21: 'COOK COUNTY . . . . 60.5% 71.8% 86.0% 74.1% 78.3%'; note: 'Clearance Rate Percentage equals the number of closed cases divided by the sum of new filed and reinstated cases'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0040: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_26 (required, +10 pts), "source" field.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf at p.22; pincite: p.22.

Cited for: Cook County civil-category clearance rate 97.9%

Quotes: []

Context: 2023 Annual Report Statistical Summary.pdf at p.22

Fictional by design: False; 

### First check: VERIFIED

Report p.22 ('Clearance Rates by Circuit, Civil Category') shows Cook County 97.9% for 2023.

Excerpt read: Report p.22: 'COOK COUNTY . . . . 97.9% 68.8% 103.6% 89.7% 95.7%'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0041: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_27 (required, +10 pts), "source" field.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf at p.22.; pincite: p.22.

Cited for: 18th Circuit civil-category clearance rate 96.3%

Quotes: []

Context: 2023 Annual Report Statistical Summary.pdf at p.22.

Fictional by design: False; 

### First check: VERIFIED

Report p.22 shows the 18th Circuit at 96.3% for 2023 (civil category).

Excerpt read: Report p.22: '18th . . . . 96.3% 108.1% 99.3% 94.6% 95.0%'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0042: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_28 (required, +10 pts), "source" field.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf at p. 163.; pincite: p.163.

Cited for: Cook County did not report time-to-verdict data for 2023

Quotes: []

Context: 2023 Annual Report Statistical Summary.pdf at p. 163.

Fictional by design: False; 

### First check: VERIFIED

Report p.163 (and p.160) carries the note and zero Cook entries.

Excerpt read: Report p.163: 'Note: Cook County did not report time lapse of all cases closed by jury or bench trial in 2023.' ... 'COOK Cook County 0 0.0 0 0.0'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0043: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_29 (required, +10 pts), "source" field.

Authority type: case; as written: First Nat. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.3); pincite: p.3.

Cited for: Defendants offered no evidence DuPage would resolve the case faster

Quotes: []

Context: First Nat. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Proposition supported (Guerine p.3). The party name 'First Nat. Bank' matches the West N.E.2d caption ('FIRST NATIONAL BANK et al.') but not the Illinois Reports text or the supplied attachment ('First American Bank'), and conflicts with the rubric's own 'First Am. Bank' elsewhere; a caption variant, not a different case.

Excerpt read: Supplied Guerine opinion PDF p.3: 'Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly.' N.E.2d caption on CourtListener 2056494: 'FIRST NATIONAL BANK et al., Appellants, v. Richard GUERINE et al., Appellees.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0044: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_1 (required, +3 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary's Hospital.pdf at p.3); pincite: p.3.

Cited for: Response supported by affidavit of Liam Vance

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary’s Hospital.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED

Bradbury p.3 describes the plaintiff's response supported by an affidavit and the defendants' unsupported motion; the cite supports the evidentiary role of affidavits.

Excerpt read: Supplied Bradbury opinion PDF p.3: 'For her part, the plaintiff filed an unverified response supported by a single affidavit.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0045: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_2 (required, +3 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary's Hospital.pdf at p.3); pincite: p.3.

Cited for: Response supported by affidavit of Savannah Brooks

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary’s Hospital.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED

Bradbury p.3 describes the plaintiff's response supported by an affidavit and the defendants' unsupported motion; the cite supports the evidentiary role of affidavits.

Excerpt read: Supplied Bradbury opinion PDF p.3: 'For her part, the plaintiff filed an unverified response supported by a single affidavit.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0046: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_3 (required, +3 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary's Hospital.pdf at p.3); pincite: p.3.

Cited for: Response supported by affidavit of Caleb Montgomery

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary’s Hospital.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED

Bradbury p.3 describes the plaintiff's response supported by an affidavit and the defendants' unsupported motion; the cite supports the evidentiary role of affidavits.

Excerpt read: Supplied Bradbury opinion PDF p.3: 'For her part, the plaintiff filed an unverified response supported by a single affidavit.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0047: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_4 (required, +3 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary's Hospital.pdf at p.3); pincite: p.3.

Cited for: Response supported by affidavit of Maya Linwood

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary’s Hospital.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED

Bradbury p.3 describes the plaintiff's response supported by an affidavit and the defendants' unsupported motion; the cite supports the evidentiary role of affidavits.

Excerpt read: Supplied Bradbury opinion PDF p.3: 'For her part, the plaintiff filed an unverified response supported by a single affidavit.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0048: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_5 (required, +3 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary's Hospital.pdf at p.3); pincite: p.3.

Cited for: Response supported by affidavit of Garrett Hayes

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary’s Hospital.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED

Bradbury p.3 describes the plaintiff's response supported by an affidavit and the defendants' unsupported motion; the cite supports the evidentiary role of affidavits.

Excerpt read: Supplied Bradbury opinion PDF p.3: 'For her part, the plaintiff filed an unverified response supported by a single affidavit.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0049: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_6 (required, +3 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Affidavit of Liam Vance that DuPage would be inconvenient, "as required under Langenhorst"

Quotes: []

Context: Identifies in Assignment #2 that the affidavit by Liam Vance indicates that DuPage County would be an inconvenient forum for him to litigate this case as required under Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

Assignment-2 criterion_6 turns a useful rebuttal affidavit into something 'required under Langenhorst.' At PDF p.10 the majority discusses missing affidavits about inconvenience in the plaintiff's chosen St. Clair forum and puts the transfer burden on defendants. It does not require physician or plaintiff affidavits proving inconvenience in the proposed DuPage forum. The criterion's literal legal attribution is overstated, although the affidavit could be relevant evidence.

Excerpt read: Langenhorst attachment PDF pp.7,10: defendants must prove the chosen forum inconvenient and another more convenient to all; p.10 discusses absent affidavits about St. Clair, the chosen forum.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0050: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_6 (required, +3 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10); pincite: p.10.

Cited for: Affidavit of Liam Vance that DuPage would be inconvenient, "as required under Langenhorst"

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

The source field correctly identifies Langenhorst and PDF p.10, but it is offered to support criterion_6's assertion that Liam Vance's DuPage-inconvenience affidavit is required. Page 10 imposes no such plaintiff or witness affidavit requirement; the burden remains with defendants. This is one underlying proposition defect repeated in a separate rubric field.

Excerpt read: Langenhorst attachment PDF p.10: the court discusses missing affidavits that St. Clair County, the chosen forum, inconvenienced witnesses and restates the defendants' burden.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0051: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_7 (required, +3 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Affidavit of Savannah Brooks that DuPage would be inconvenient, "as required under Langenhorst"

Quotes: []

Context: Identifies in Assignment #2 that the affidavit by Savannah Brooks indicates that DuPage County would be an inconvenient forum for her to litigate this case as required under Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

Criterion_7 repeats the unsupported requirement for Savannah Brooks's affidavit. Langenhorst makes her DuPage inconvenience potentially relevant, but assigns no duty to her or plaintiff to file such an affidavit.

Excerpt read: Langenhorst attachment PDF pp.7,10: the defendants carry the transfer burden; p.10 addresses affidavits about the chosen St. Clair forum.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0052: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_7 (required, +3 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10); pincite: p.10.

Cited for: Affidavit of Savannah Brooks that DuPage would be inconvenient, "as required under Langenhorst"

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

Criterion_7's source field supplies an accurate case and page locator for an inaccurate required-affidavit proposition. Page 10 concerns the chosen forum and the defendants' burden, not an obligation for Savannah Brooks to demonstrate DuPage inconvenience.

Excerpt read: Langenhorst attachment PDF p.10: absence of St. Clair-inconvenience affidavits and defendants' burden; no Brooks or transferee-forum affidavit rule.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0053: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_8 (required, +3 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Affidavit of Caleb Montgomery that DuPage would be inconvenient, "as required under Langenhorst"

Quotes: []

Context: Identifies in Assignment #2 that the affidavit by Caleb Montgomery indicates that DuPage County would be an inconvenient forum for him to litigate this case as required under Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

Criterion_8 says Caleb Montgomery's affidavit showing DuPage inconvenience is required under Langenhorst. The decision never imposes that requirement on a plaintiff-side physician; it makes the defendants prove transfer is more convenient to all parties.

Excerpt read: Langenhorst attachment PDF pp.7,10: defendants bear the burden; absent affidavits related to chosen St. Clair, not proposed Clinton County.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0054: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_8 (required, +3 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10); pincite: p.10.

Cited for: Affidavit of Caleb Montgomery that DuPage would be inconvenient, "as required under Langenhorst"

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

The criterion_8 source field repeats a valid Langenhorst p.10 locator as support for the invalid claim that Caleb Montgomery's DuPage-inconvenience affidavit is legally required. The page says no such thing.

Excerpt read: Langenhorst attachment PDF p.10: chosen-forum witness affidavits discussed; defendants' obligation to show transfer convenient to all parties restated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0055: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_9 (required, +3 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Affidavit of Maya Linwood that DuPage would be inconvenient, "as required under Langenhorst"

Quotes: []

Context: Identifies in Assignment #2 that the affidavit by Maya Linwood indicates that DuPage County would be an inconvenient forum for her to litigate this case as required under Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

Criterion_9 attributes to Langenhorst a requirement that Maya Linwood establish proposed DuPage inconvenience by affidavit. The opinion puts the burden on defendants and does not require a plaintiff-side physician affidavit, though the evidence could rebut transfer.

Excerpt read: Langenhorst attachment PDF pp.7,10: transfer burden on defendants; no requirement for plaintiff-side affidavits about the proposed forum.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0056: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_9 (required, +3 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10); pincite: p.10.

Cited for: Affidavit of Maya Linwood that DuPage would be inconvenient, "as required under Langenhorst"

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

The p.10 source citation in criterion_9 is a correct locator but does not support the criterion's claimed legal requirement for Maya Linwood's DuPage-inconvenience affidavit. This repeats the criterion-field proposition defect.

Excerpt read: Langenhorst attachment PDF p.10: court discusses absence of chosen-forum inconvenience affidavits and reiterates defendants' transfer burden.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0057: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_10 (required, +3 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Affidavit of Garrett Hayes that DuPage would be inconvenient, "as required under Langenhorst"

Quotes: []

Context: Identifies in Assignment #2 that the affidavit by Garrett Hayes indicates that DuPage County would be an inconvenient forum for him to litigate this case as required under Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

Criterion_10 incorrectly calls Garrett Hayes's showing that DuPage would inconvenience him required by Langenhorst. The decision treats comparative convenience as relevant, but does not require a plaintiff-side witness affidavit.

Excerpt read: Langenhorst attachment PDF pp.7,10: defendants must demonstrate the chosen forum is inconvenient and their alternative more convenient to all; p.10 concerns chosen St. Clair.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0058: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_10 (required, +3 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10); pincite: p.10.

Cited for: Affidavit of Garrett Hayes that DuPage would be inconvenient, "as required under Langenhorst"

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

Criterion_10's source field cites the right Langenhorst page for a proposition it does not contain. Garrett Hayes's proposed-forum inconvenience could matter, but Langenhorst does not require his affidavit.

Excerpt read: Langenhorst attachment PDF p.10: no affidavits about the chosen St. Clair forum and burden on defendants; no proposed-forum affidavit mandate.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0059: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_11 (required, +5 pts), "source" field.

Authority type: case; as written: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary's Hospital.pdf at p.3); pincite: p.3.

Cited for: Response supported by plaintiff Sara Davis's affidavit

Quotes: []

Context: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) (Bradbury v. St. Mary’s Hospital.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED

Bradbury p.3 describes the response affidavit and the unsupported motion.

Excerpt read: Supplied Bradbury opinion PDF p.3: 'For her part, the plaintiff filed an unverified response supported by a single affidavit.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0060: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_12 (required, +5 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Plaintiff's affidavit that DuPage would be inconvenient, "as required under Langenhorst"

Quotes: []

Context: Identifies in Assignment #2 that the affidavit by the Plaintiff, Sara Davis, indicates that DuPage County would be an inconvenient forum for her to litigate this case as required under Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

Criterion_12 says plaintiff Sara Davis's DuPage-inconvenience affidavit is required under Langenhorst. The opinion says defendants cannot assert the chosen forum inconveniences the plaintiff and must establish that another forum is more convenient to all parties. It does not shift an affidavit burden to Sara.

Excerpt read: Langenhorst attachment PDF pp.7,9-10: defendants cannot claim plaintiff's chosen forum inconveniences plaintiff; defendants must show an alternative more convenient to all.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0061: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_12 (required, +5 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10); pincite: p.10.

Cited for: same

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Langenhorst (attachment pp.3, 7, 10) places the burden on the defendant to show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties; it observes that no affidavits said the CHOSEN forum (St. Clair) was inconvenient. It contains no requirement that a plaintiff or plaintiff's witnesses file affidavits that the TRANSFEREE forum would be inconvenient. The criterion's 'as required under Langenhorst' therefore attributes to Langenhorst a requirement it does not state. Such affidavits may be strategically useful (they rebut the 'more convenient to all parties' prong), so a second check should weigh whether 'as required' can fairly be read as 'as relevant under'.

Excerpt read: Supplied Langenhorst opinion PDF p.10: 'In this case, no affidavits have been filed stating that St. Clair County would be an inconvenient forum for any of the witnesses. ... We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

Criterion_12's Langenhorst p.10 source field points to a real passage but does not substantiate a legal requirement that Sara Davis file an affidavit about inconvenience in DuPage. It repeats the criterion's overstated attribution.

Excerpt read: Langenhorst attachment PDF p.10: absence of affidavits about St. Clair, the chosen forum; defendants' transfer burden reiterated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0062: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_13 (required, +5 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill.2d 430 (2006); pincite: .

Cited for: FNC is a discretionary power exercised only in exceptional circumstances

Quotes: []

Context: Mentions in Assignment #2 that the forum non conveniens doctrine gives courts discretionary power that should be exercised only in exceptional circumstances when the interests of justice require a trial in a more convenient forum under Langenhorst v. Norfolk S. Ry. Co., 219 Ill.2d 430 (2006).

Fictional by design: False; 

### First check: VERIFIED

Langenhorst p.6 states it.

Excerpt read: Supplied Langenhorst opinion PDF p.6: 'the forum non conveniens doctrine gives courts discretionary power that should be exercised only in exceptional circumstances when the interests of justice require a trial in a more convenient forum.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0063: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_13 (required, +5 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.6); pincite: p.6.

Cited for: same

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.6).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the passage.

Excerpt read: Supplied Langenhorst opinion PDF p.6: 'discretionary power that should be exercised only in exceptional circumstances'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0064: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_14 (required, +5 pts), "criterion" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002); pincite: .

Cited for: Test is whether the relevant factors, viewed in their totality, strongly favor transfer to defendant's forum

Quotes: []

Context: Mentions in Assignment #2 that the test is whether the relevant factors, viewed in their totality, strongly favor transfer to the forum suggested by defendant under First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Guerine supports the substance (p.4: 'whether the defendant has proven that the balance of factors strongly favors transfer'; p.7 quoting Hinshaw: 'the factors, when viewed in their totality, must strongly favor transfer'), but the exact formulation is Griffith's (136 Ill. 2d at 108), quoted in Dawdy and in Langenhorst p.6, not Guerine's.

Excerpt read: Supplied Guerine opinion PDF p.7: '"the factors, when viewed in their totality, must strongly favor transfer." (Emphasis in original.) Hinshaw' Griffith (CourtListener 2196019): 'The test, then, is whether the relevant factors, viewed in their totality, strongly favor transfer to the forum suggested by defendant.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0065: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_14 (required, +5 pts), "source" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.7); pincite: p.7.

Cited for: same

Quotes: []

Context: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.7).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Guerine p.7 contains the Hinshaw quotation with 'viewed in their totality'; the criterion's exact test wording is Griffith's.

Excerpt read: Supplied Guerine opinion PDF p.7: 'the factors, when viewed in their totality, must strongly favor transfer.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0066: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_15 (required, +3 pts), "source" field.

Authority type: case; as written: First Nat. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.8); pincite: p.8.

Cited for: Balance of factors must strongly favor transfer before plaintiff is deprived of chosen forum

Quotes: []

Context: First Nat. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.8).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Proposition supported verbatim at Guerine p.8. 'First Nat. Bank' is the West N.E.2d caption variant; the Illinois Reports text and the attachment say 'First American Bank'.

Excerpt read: Supplied Guerine opinion PDF p.8: 'The balance of factors must strongly favor transfer of the case before the plaintiff can be deprived of his chosen forum.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0067: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_16 (required, +5 pts), "criterion" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002); pincite: .

Cited for: Plaintiff has a substantial interest in choosing the forum where his rights will be vindicated

Quotes: []

Context: Identifies in Assignment #2 that the plaintiff has a substantial interest in choosing the forum where his rights will be vindicated under First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002).

Fictional by design: False; 

### First check: VERIFIED

Guerine p.3 states it.

Excerpt read: Supplied Guerine opinion PDF p.3: 'The plaintiff has a substantial interest in choosing the forum where his rights will be vindicated'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0068: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_16 (required, +5 pts), "source" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.3); pincite: p.3.

Cited for: same

Quotes: []

Context: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED

Cited page contains the passage.

Excerpt read: Supplied Guerine opinion PDF p.3: 'The plaintiff has a substantial interest in choosing the forum where his rights will be vindicated'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0069: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_17 (required, +3 pts), "criterion" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006); pincite: .

Cited for: Court congestion is a relatively insignificant factor

Quotes: []

Context: States in Assignment #2 that the issue of court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly, under Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006).

Fictional by design: False; 

### First check: VERIFIED

Langenhorst p.11 quotes Guerine's statement.

Excerpt read: Supplied Langenhorst opinion PDF p.11: '"Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly."'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0070: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_17 (required, +3 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10); pincite: p.10.

Cited for: same

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co., 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.10).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The quoted congestion rule is on attachment p.11, not p.10 (p.10 ends with the docket discussion's first sentence).

Excerpt read: Supplied Langenhorst opinion PDF p.11: 'Court congestion is a relatively insignificant factor'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0071: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_18 (penalty, -30 pts), "source" field.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf at p.21; pincite: p.21.

Cited for: Cook County 60.5% clearance (penalized)

Quotes: []

Context: 2023 Annual Report Statistical Summary.pdf at p.21

Fictional by design: False; 

### First check: VERIFIED

Report p.21 shows Cook County 60.5% (all case types).

Excerpt read: Report p.21: 'COOK COUNTY . . . . 60.5%'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0072: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_19 (required, +1 pts), "source" field.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf at p.21; pincite: p.21.

Cited for: DuPage (18th Circuit) civil clearance 96.3%

Quotes: []

Context: 2023 Annual Report Statistical Summary.pdf at p.21

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

96.3% is the 18th Circuit civil-category rate on p.22; p.21 is the all-case-types table (18th Circuit 99.0%).

Excerpt read: Report p.22: '18th . . . 96.3%'; p.21: '18th . . . 99.0%'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0073: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_20 (required, +1 pts), "source" field.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf at p.21; pincite: p.21.

Cited for: Cook County civil clearance 97.9%

Quotes: []

Context: 2023 Annual Report Statistical Summary.pdf at p.21

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

97.9% is on p.22 (civil category); p.21 shows Cook County 60.5% (all case types).

Excerpt read: Report p.22: 'COOK COUNTY . . . . 97.9%'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0074: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_23 (penalty, -30 pts), "source" field.

Authority type: case; as written: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.7); pincite: p.7.

Cited for: Burden is on defendant, not plaintiff (penalized statement that plaintiff met its burden)

Quotes: []

Context: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006), (Langenhorst v. Norfolk Southern.pdf at p.7).

Fictional by design: False; 

### First check: VERIFIED

Langenhorst p.7 places the burden on the defendant.

Excerpt read: Supplied Langenhorst opinion PDF p.7: 'The burden is on the defendant to show that relevant private and public interest factors "strongly favor" the defendant's choice of forum to warrant disturbing plaintiff's choice.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0075: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: assignment-2 rubric (tests/fixtures/rubric.json); location: assignment-2 criterion_24 (penalty, -30 pts), "source" field.

Authority type: case; as written: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.3); pincite: p.3.

Cited for: Nonresident plaintiff receives less, not no, deference (penalized statement)

Quotes: []

Context: First Am. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) (First Am Bank v. Guerine.pdf at p.3).

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Supporting language ('somewhat less deference'; Elling 'only less, as opposed to none') is at Guerine p.4; p.3 has the substantial-interest sentence.

Excerpt read: Supplied Guerine opinion PDF p.4: 'nonetheless the deference to be accorded is only less, as opposed to none'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0076: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: assignment-1 rubric (tests/fixtures/rubric.json); location: assignment-1 criterion_25 (penalty, -30 pts), "justification" field.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf, p. 21; pincite: p.21.

Cited for: The 60.5% figure is overall clearance, not the civil (> $50,000) comparison

Quotes: []

Context: t's weak, and flag any points we should target in our response." This information is stated in the 2023 Annual Report Statistical Summary.pdf, p. 21, however, this is a statistic that refers to overall clearance, and is not applicable to Civil Cases, specifically Civil Case in excess of $50,000.00 which is the comparison necessary to assist the Court in completing the analysis to grant Defendant's Motion to Transfer.

Fictional by design: False; 

### First check: VERIFIED

Report p.21 is the all-case-types clearance table (Cook 60.5%); the civil-category table is p.22. The justification's characterization is correct.

Excerpt read: Report p.21 heading: '2023 CLEARANCE RATES BY CIRCUIT ALL CASE TYPES'; 'COOK COUNTY . . . . 60.5%'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0077: Davis v. Smith, No. 2025 L 5841 (scenario case)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 1, caption.

Authority type: case; as written: Sara Davis v. John Smith, M.D., et al., No. 2025 L 5841 (Cir. Ct. Cook County); pincite: .

Cited for: Scenario case caption

Quotes: []

Context: 

Fictional by design: True; Fictional scenario lawsuit and docket number.

### First check: excluded by design


### Second check: not required


## FNC-0078: Davis v. Smith, No. 2025 L 5841 (scenario case)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 8, caption of Exhibit A (Affidavit of John Smith, M.D.).

Authority type: case; as written: Sara Davis v. John Smith, M.D., et al., No. 2025 L 5841 (Cir. Ct. Cook County); pincite: .

Cited for: Scenario case caption

Quotes: []

Context: 

Fictional by design: True; Fictional scenario lawsuit and docket number.

### First check: excluded by design


### Second check: not required


## FNC-0079: Davis v. Smith, No. 2025 L 5841 (scenario case)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 10, caption of Exhibit B (Affidavit of Safe Hospital administrator).

Authority type: case; as written: Sara Davis v. John Smith, M.D., et al., No. 2025 L 5841 (Cir. Ct. Cook County); pincite: .

Cited for: Scenario case caption

Quotes: []

Context: 

Fictional by design: True; Fictional scenario lawsuit and docket number.

### First check: excluded by design


### Second check: not required


## FNC-0080: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 1, Introduction ¶1.

Authority type: case; as written: First Am Bank v. Guerine.pdf, p.2, ¶5; pincite: p.2 ¶5.

Cited for: FNC allows declining jurisdiction in the exceptional case where another forum would better serve the ends of justice

Quotes: ['allows a trial court to decline jurisdiction in the exceptional case where trial in another forum with proper jurisdiction and venue ‘would better serve the ends of justice.’']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Guerine verbatim (attachment p.2; Illinois Reports text 198 Ill. 2d at 515).

Excerpt read: Supplied Guerine opinion PDF p.2: 'which allows a trial court to decline jurisdiction in the exceptional case where trial in another forum with proper jurisdiction and venue “would better serve the ends of justice”'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0081: 735 ILCS 5/2-622 (healing art malpractice affidavit and report)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 2, Background ¶8.

Authority type: statute; as written: 735 ILCS 5/2-622 report; pincite: .

Cited for: Identifies the reviewing physician's report attached to the complaint

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 'the reviewing health professional has determined in a written report ... that there is a reasonable and meritorious cause for the filing of such action'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073500050K2-622.htm

### Second check: not required


## FNC-0082: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶1.

Authority type: case; as written: Langenhorst v. Norfolk Southern.pdf, p.5, discussing Vinson v. Allstate; pincite: p.5.

Cited for: FNC is an equitable doctrine founded in fundamental fairness and sensible administration of justice

Quotes: ['Forum non conveniens is an equitable doctrine founded in considerations of fundamental fairness and the sensible and effective administration of justice.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted sentence appears verbatim in Langenhorst p.5 (citing Vinson, 144 Ill. 2d at 310).

Excerpt read: Supplied Langenhorst opinion PDF p.5: 'Forum non conveniens is an equitable doctrine founded in considerations of fundamental fairness and the sensible and effective administration of justice.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0083: Vinson v. Allstate, 144 Ill. 2d 306, 579 N.E.2d 857 (1991)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶1 (embedded).

Authority type: case; as written: Vinson v. Allstate (as discussed in Langenhorst p.5); pincite: .

Cited for: Same proposition (source of Langenhorst's statement)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Vinson states the doctrine (quoting Adkins: 'founded in considerations of fundamental fairness and sensible and effective judicial administration'); Langenhorst's paraphrase is fair.

Excerpt read: 'a court ... may nevertheless decline jurisdiction of a case when it is apparent that trial in another forum ... would be more convenient and would better serve the ends of justice.'; 'the fact that Allstate conducts business within the county is not the only factor the court should consider in its analysis.'

- https://www.courtlistener.com/opinion/2238079/vinson-v-allstate/

### Second check: not required


## FNC-0084: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶1.

Authority type: case; as written: Langenhorst v. Norfolk Southern.pdf, p.5, discussing Bland v. Norfolk & Western Ry. Co.; pincite: p.5.

Cited for: FNC causes a court to look beyond the criterion of venue to relative convenience

Quotes: ['causes a court to look beyond the criterion of venue', 'the relative convenience of a forum']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quoted phrases appear in Langenhorst p.5 quoting Bland, 116 Ill. 2d at 226.

Excerpt read: Supplied Langenhorst opinion PDF p.5: 'A forum non conveniens motion “causes a court to look beyond the criterion of venue when it considers the relative convenience of a forum.”'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0085: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217, 506 N.E.2d 1291 (1987)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶1 (embedded).

Authority type: case; as written: Bland v. Norfolk & Western Ry. Co. (as discussed in Langenhorst p.5); pincite: .

Cited for: Same proposition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Phrase located in Bland (116 Ill. 2d at 226).

Excerpt read: Bland: 'A forum non conveniens motion "assumes that both courts can obtain jurisdiction over the defendant" and causes a court to look beyond the criterion of venue when it considers the relative convenience of a forum.'

- https://www.courtlistener.com/opinion/2210166/bland-v-norfolk-western-railway-co/

### Second check: not required


## FNC-0086: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶1.

Authority type: case; as written: Bradbury v. St. Marys Hospital.pdf, p.2, ¶5; pincite: p.2 ¶5.

Cited for: Intrastate FNC presupposes more than one proper venue and focuses on relative convenience

Quotes: ["intrastate application of the doctrine of forum non conveniens presupposes the existence of more than one proper venue within the State and focuses the inquiry upon the relative convenience of the plaintiff's chosen venue."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Bradbury p.2 verbatim.

Excerpt read: Supplied Bradbury opinion PDF p.2: 'The intrastate application of the doctrine of forum non conveniens presupposes the existence of more than one proper venue within the State and focuses the inquiry upon the relative convenience of the plaintiff's chosen venue.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0087: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶2.

Authority type: case; as written: Bradbury v. St. Marys Hospital.pdf, p.2, ¶5; pincite: p.2 ¶5.

Cited for: Trial court applies an uneven balancing test to private and public factors

Quotes: ['must apply an uneven balancing test to various private interest factors affecting the convenience of the litigants and public interest factors affecting the administration of the courts.']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Bradbury says resolution 'requires the court to apply an uneven balancing test ...'; the motion places 'must apply' inside the quotation marks. Substance accurate; quoted wording slightly altered.

Excerpt read: Supplied Bradbury opinion PDF p.2: 'The resolution of a forum non conveniens motion requires the court to apply an uneven balancing test to various private interest factors affecting the convenience of the litigants and public interest factors affecting the administration of the courts.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0088: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶2.

Authority type: case; as written: First Am Bank v. Guerine.pdf, p.3, ¶4; pincite: p.3 ¶4.

Cited for: Private interest factors

Quotes: ['(1) the convenience of the parties; (2) the relative ease of access to sources of testimonial, documentary, and real evidence; and (3) all other practical problems that make trial of a case easy, expeditious, and inexpensive.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Guerine p.3 (truncated before the 'for example' clause).

Excerpt read: Supplied Guerine opinion PDF p.3: 'the private interest factors include (1) the convenience of the parties; (2) the relative ease of access to sources of testimonial, documentary, and real evidence; and (3) all other practical problems that make trial of a case easy, expeditious, and inexpensive'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0089: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶2.

Authority type: case; as written: First Am Bank v. Guerine.pdf, p.3, ¶4; pincite: p.3 ¶4.

Cited for: Public interest factors

Quotes: ['(1) the interest in deciding localized controversies locally; (2) the unfairness of imposing the expense of a trial and the burden of jury duty on residents of a county with little connection to the litigation; and (3) the administrative difficulties presented by adding further litigation to court dockets in already congested fora.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Guerine p.3.

Excerpt read: Supplied Guerine opinion PDF p.3: 'The public interest factors include (1) the interest in deciding localized controversies locally; (2) the unfairness of imposing the expense of a trial and the burden of jury duty on residents of a county with little connection to the litigation; and (3) the administrative difficulties presented by adding further litigation to court dockets in already congested fora.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0090: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶3.

Authority type: case; as written: Langenhorst v. Norfolk Southern.pdf, p.7, ¶2; pincite: p.7 ¶2.

Cited for: Defendant bears burden to show factors strongly favor its forum

Quotes: ["The burden is on the defendant to show that relevant private and public interest factors ‘strongly favor‘ the defendant's choice of forum to warrant disturbing plaintiff's choice."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Langenhorst p.7.

Excerpt read: Supplied Langenhorst opinion PDF p.7: 'The burden is on the defendant to show that relevant private and public interest factors "strongly favor" the defendant's choice of forum to warrant disturbing plaintiff's choice.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0091: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶3.

Authority type: case; as written: First Am Bank v. Guerine.pdf, p.4, ¶3; pincite: p.4 ¶3.

Cited for: Factors not weighed against each other; total circumstances must strongly favor transfer

Quotes: ['the trial court must evaluate the total circumstances of the case in determining whether the defendant has proven that the balance of factors strongly favors transfer.']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Guerine p.4 reads 'in deciding whether the defendant has proven ...'; the motion's quotation ('in determining whether') tracks Langenhorst's restatement, not Guerine's wording.

Excerpt read: Supplied Guerine opinion PDF p.4: 'the trial court must evaluate the total circumstances of the case in deciding whether the defendant has proven that the balance of factors strongly favors transfer.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0092: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶3.

Authority type: case; as written: Langenhorst v. Norfolk Southern.pdf, p.7, ¶2; pincite: p.7 ¶2.

Cited for: Same

Quotes: ['the trial court must evaluate the total circumstances of the case in determining whether the defendant has proven that the balance of factors strongly favors transfer.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Langenhorst p.7 verbatim.

Excerpt read: Supplied Langenhorst opinion PDF p.7: 'rather, the trial court must evaluate the total circumstances of the case in determining whether the defendant has proven that the balance of factors strongly favors transfer.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0093: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶3.

Authority type: case; as written: First Am Bank v. Guerine.pdf, p.4, ¶3; pincite: p.4 ¶3.

Cited for: Defendant must show chosen forum inconvenient to it and another forum more convenient to all; cannot assert plaintiff's inconvenience

Quotes: ["must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties", "cannot assert that the plaintiff's chosen forum is inconvenient to the plaintiff."]

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Guerine p.4: 'The defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and another forum is more convenient to all parties.' The motion's quotation inserts 'that' before 'another' (Langenhorst p.7's wording). Second quotation matches.

Excerpt read: Supplied Guerine opinion PDF p.4: 'The defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and another forum is more convenient to all parties. ... The defendant cannot assert that the plaintiff's chosen forum is inconvenient to the plaintiff.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0094: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶4.

Authority type: case; as written: First Am Bank v. Guerine.pdf, p.4, ¶1; pincite: p.4 ¶1.

Cited for: Deference reduced when neither residence nor accident site is in chosen forum

Quotes: ["when neither the plaintiff's residence nor the site of the accident or injury is located in the chosen forum."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Guerine p.4.

Excerpt read: Supplied Guerine opinion PDF p.4: 'the plaintiff's interest in choosing the forum receives somewhat less deference when neither the plaintiff's residence nor the site of the accident or injury is located in the chosen forum.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0095: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶4.

Authority type: case; as written: First Am Bank v. Guerine.pdf, p.4, ¶1; pincite: p.4 ¶1.

Cited for: Foreign plaintiff's choice deserves less deference

Quotes: ["When the plaintiff is foreign to the forum chosen ... this assumption is much less reasonable and the plaintiff's choice deserves less deference."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation (with ellipsis) matches Guerine p.4 quoting Wieser, 98 Ill. 2d at 367.

Excerpt read: Supplied Guerine opinion PDF p.4: 'When the plaintiff is foreign to the forum chosen, however, this assumption is much less reasonable and the plaintiff's choice deserves less deference.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0096: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶4.

Authority type: case; as written: Bradbury v. St. Marys Hospital.pdf, p.3, ¶3; pincite: p.3 ¶3.

Cited for: In wrongful death, decedent's residence at death matters

Quotes: ["it is the decedent's residence at the time of death that is of significance"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Bradbury p.3.

Excerpt read: Supplied Bradbury opinion PDF p.3: 'In a wrongful death action, it is the decedent's residence at the time of death that is of significance.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0097: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 3, Legal Standard ¶4 (continuing to p.4).

Authority type: case; as written: Bradbury v. St. Marys Hospital.pdf, p.4, ¶6; pincite: p.4 ¶6.

Cited for: Without record of residence, deference cannot be weighed

Quotes: ["we do not know the residence of the decedent at the time of his death to determine the level of deference that should be accorded to the plaintiff's choice of forum"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Bradbury p.4 (last paragraph).

Excerpt read: Supplied Bradbury opinion PDF p.4: 'Lastly, and most importantly, we do not know the residence of the decedent at the time of his death to determine the level of deference that should be accorded to the plaintiff's choice of forum.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0098: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 4, Part IV.A.

Authority type: case; as written: First Am Bank v. Guerine.pdf, p.7, ¶3; pincite: p.7 ¶3.

Cited for: Guerine found transfer unwarranted in part because a defendant lived in Cook County

Quotes: ['lives in Cook County and never filed a forum non conveniens motion', 'Cook County is a more convenient forum for all parties']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotations appear in Guerine p.7 (second truncated before 'especially the defendants').

Excerpt read: Supplied Guerine opinion PDF p.7: 'On the defense side, Guerine lives in Cook County and never filed a forum non conveniens motion. ... Cook County is a more convenient forum for all parties, especially the defendants.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0099: Ill. S. Ct. R. 237

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 4, Part IV.C.

Authority type: court_rule; as written: Illinois Supreme Court Rule 237; pincite: .

Cited for: Compulsory process available for in-state witnesses regardless of venue

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 237 governs compelling witnesses' appearance at trial; Bradbury p.4 applies it the same way.

Excerpt read: 'Rule 237. Compelling Appearances of Witnesses at Trial. (a) Service of Subpoenas. Any witness shall respond to any lawful subpoena ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0100: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 4, Part IV.C.

Authority type: case; as written: see Bradbury v. St. Marys Hospital.pdf, p.4, ¶2; pincite: p.4 ¶2.

Cited for: Process available in either county under Rule 237

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Bradbury p.4 so states.

Excerpt read: Supplied Bradbury opinion PDF p.4: 'process would be available in either county to compel the attendance of any unwilling Illinois resident witnesses pursuant to Supreme Court Rule 237'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0101: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF pages 4-5, Part IV.D.

Authority type: case; as written: Guerine (Part IV.D: "in each of which the Illinois Supreme Court denied transfer"); First Am Bank v. Guerine.pdf, p.8, ¶4; pincite: p.8 ¶4.

Cited for: Guerine "held that transfer is warranted only where" witnesses are scattered and no county predominates

Quotes: ["the potential trial witnesses are scattered among several counties, including the plaintiff's chosen forum, and no single county enjoys a predominant connection to the litigation."]

Context: Guerine witness counties (Cook, De Kalb, Kane, Du Page, Winnebago) are accurately listed (Guerine pp.1, 7-8).

Fictional by design: False; 

### First check: MISCHARACTERIZED

Inverts Guerine's holding. Guerine p.8 holds that a trial court ABUSES ITS DISCRETION IN GRANTING transfer where the witnesses are scattered among several counties including the chosen forum and no county predominates; the motion says Guerine held transfer is 'warranted only where' those conditions exist. The quoted words are accurate; the framing reverses their meaning. (The motion's next sentences use the holding correctly, so the error may be a drafting slip, but as written it misstates the holding.)

Excerpt read: Supplied Guerine opinion PDF p.8: 'we hold that a trial court abuses its discretion in granting an intrastate forum non conveniens motion to transfer venue where, as here, the potential trial witnesses are scattered among several counties, including the plaintiff's chosen forum, and no single county enjoys a predominant connection to the litigation.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: MISCHARACTERIZED

The defense motion quotes Guerine's witness pattern accurately but introduces it as a condition where transfer is 'warranted only.' Guerine's holding is the inverse: granting transfer on that pattern is an abuse of discretion. The motion's later application points in the right direction, suggesting a drafting slip, but it does not cure the sentence as written. First American/First National caption variation is not a defect.

Excerpt read: Guerine attachment PDF p.8: court holds transfer on the scattered-witness/no-predominant-county pattern is an abuse of discretion; motion PDF p.5 calls transfer on that pattern warranted.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Defendants%20Motion%20to%20Transfer.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0102: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 5, Part IV.D.

Authority type: case; as written: Langenhorst v. Norfolk Southern.pdf, p.10-p.11; pincite: pp.10-11.

Cited for: Langenhorst majority found witnesses dispersed with no predominant connection

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Langenhorst pp.8-11 so find (witnesses in several Illinois counties, Indiana, and Missouri; 'no single county enjoys a predominant connection').

Excerpt read: Supplied Langenhorst opinion PDF p.11: 'most of the potential trial witnesses are scattered and no single county enjoys a predominant connection to the litigation.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0103: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 5, Part V.A.

Authority type: case; as written: Compare Bradbury v. St. Marys Hospital.pdf, p.2, ¶5; pincite: p.2 ¶5.

Cited for: Cook interest from death; Kankakee interest from negligence within its borders

Quotes: ['the action involves alleged acts of medical negligence occurring within its borders']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Quoted language is accurate but appears on Bradbury attachment p.4, not p.2. The motion's surrounding argument ('unlike in Bradbury, did not result from any Cook County conduct') is advocacy: Bradbury rested Cook County's interest on the death there, not on defendants' conduct (defendants' role in the transfer was discussed only under the Bland treating-physician point).

Excerpt read: Supplied Bradbury opinion PDF p.4: 'Kankakee County has an interest because the action involves alleged acts of medical negligence occurring within its borders, and Cook County has an interest because the decedent died here.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0104: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 5, Part V.B.

Authority type: case; as written: See First Am Bank v. Guerine.pdf, p.3, ¶4; pincite: p.3 ¶4.

Cited for: Unfairness of jury duty on unconnected county

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Guerine p.3 lists that public factor.

Excerpt read: Supplied Guerine opinion PDF p.3: 'the unfairness of imposing the expense of a trial and the burden of jury duty on residents of a county with little connection to the litigation'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0105: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 5, Part V.B.

Authority type: case; as written: Langenhorst v. Norfolk Southern.pdf, p.6-p.7; pincite: pp.6-7.

Cited for: Public interest factor: unfairness of jury duty burden

Quotes: ['the unfairness of imposing trial expense and the burden of jury duty on residents of a forum that has little connection to the litigation']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Langenhorst pp.6-7.

Excerpt read: Supplied Langenhorst opinion PDF p.6: 'the unfairness of imposing trial expense and the burden of jury duty on residents of a forum that has little connection to the litigation'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0106: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 5, Part V.C.

Authority type: case; as written: See Bradbury v. St. Marys Hospital.pdf, p.4, ¶5; pincite: p.4 ¶5.

Cited for: Judicial notice of AOIC statistics in assessing congestion

Quotes: ['judicial notice may be taken of the statistics issued by the Director of the Administrative Office of the Illinois Courts in assessing court congestion']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Bradbury p.4.

Excerpt read: Supplied Bradbury opinion PDF p.4: 'judicial notice may be taken of the statistics issued by the Director of the Administrative Office of the Illinois Courts in assessing court congestion'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0107: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 5, Part V.C (continuing to p.6).

Authority type: case; as written: Langenhorst v. Norfolk Southern.pdf, p.18; pincite: p.18.

Cited for: Langenhorst relied on AOIC Statistical Summary data comparing caseloads and time to verdict

Quotes: ['Administrative Office of the Illinois Courts, [Annual Report of the Illinois Courts], Statistical Summary']

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

The statistics passage is in Justice Garman's DISSENT (attachment p.17, carrying onto p.18; the attachment omits the dissent heading). The majority did not rely on the statistics; it deferred to the trial judge's statement that St. Clair County could try the case promptly and held defendants had not shown faster resolution in Clinton County (p.11). Presenting the dissent's reliance as the court's misstates the authority.

Excerpt read: Supplied Langenhorst opinion PDF p.17: 'Here, the 2000 annual report of the Administrative Office of the Illinois Courts, which defendants called to the circuit court's attention, reveals ...' Supplied Langenhorst opinion PDF p.11: 'the St. Clair County circuit court did not note any administrative problems ... Simply stated, the record, including the trial court's statement that court congestion in St. Clair County is not a concern, does not support defendants' contention.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: MISCHARACTERIZED

The motion describes Langenhorst p.18 as relying on AOIC statistics. Page 18 is Justice Garman's dissent, whose p.17 text expressly says the majority failed to examine those figures. The majority at pp.10-11 credited the trial judge's prompt-trial assessment and found no showing of quicker resolution after transfer. A dissent can be cited as a dissent, but the motion's unqualified attribution to Langenhorst obscures which opinion relied on the data.

Excerpt read: Langenhorst attachment PDF p.11 majority: no evidence Clinton would resolve sooner; pp.17-18 dissent: majority failed to examine statistics and dissent sets them out; PDF p.20 identifies Garman's dissent.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Defendants%20Motion%20to%20Transfer.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0108: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 6, Part V.C ¶1.

Authority type: case; as written: Bradbury v. St. Marys Hospital.pdf, p.4, ¶5; pincite: p.4 ¶5.

Cited for: Bradbury defendants never asked the court to notice statistics

Quotes: ['never requested that the trial court take notice of those statistics and never quoted any such statistics to either the trial court or to this court']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches Bradbury p.4.

Excerpt read: Supplied Bradbury opinion PDF p.4: 'we note that the defendants never requested that the trial court take notice of those statistics and never quoted any such statistics to either the trial court or to this court.'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0109: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 6, Part V.C ¶2.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf, p.21; pincite: p.21.

Cited for: Cook 60.5% vs 18th Circuit 99.0% clearance (all case types); five-year trends

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

All figures match report p.21 (Cook 78.3/74.1/86.0/71.8/60.5; 18th 100.6/82.5/110.7/102.1/99.0) and the clearance-rate definition note.

Excerpt read: Report p.21: '18th . . . 99.0% 102.1% 110.7% 82.5% 100.6%' ... 'COOK COUNTY . . . . 60.5% 71.8% 86.0% 74.1% 78.3%'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0110: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 6, Part V.C ¶3.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf, p.19, p.46, p.49; pincite: pp.19, 46, 49.

Cited for: Pending caseload figures

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cook ending open civil 145,608 and all cases 498,378 (pp.19, 49); 18th Circuit ending open civil 10,877 and all cases 101,244 (pp.19, 46).

Excerpt read: Report p.49: 'Ending Open ... 145,608 498,378'; p.46 (DuPage): 'Ending Open ... 10,877 101,244'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0111: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 6, Part V.C ¶3.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf, p.49; pincite: p.49.

Cited for: Cook case-management caveat

Quotes: ["due to changes in Cook County's case management system, there are variances in the number of cases being reported as open on January 1, 2023, when compared to the number of cases reported as open on December 31, 2022"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches the p.49 note (also on p.19).

Excerpt read: Report p.49: 'Note: Due to changes in Cook County’s case management system, there are variances in the number of cases being reported as open on January 1, 2023, when compared to the number of cases reported as open on December 31, 2022.'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0112: Administrative Office of the Illinois Courts, 2023 Annual Report of the Illinois Courts, Statistical Summary

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 6, Part V.C ¶4.

Authority type: other; as written: 2023 Annual Report Statistical Summary.pdf, p.159, p.160, p.163; pincite: pp.159, 160, 163.

Cited for: DuPage closed 17 Law > $50,000 cases by jury averaging 51.4 months; Cook did not report

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Visually inspected the original 2023 report pages 159, 160, and 163. Page 159 aligns the 17 jury dispositions and 51.4-month average with the 18th Judicial Circuit (DuPage) Law > $50,000 row. Page 163 expressly says Cook County did not report the time-lapse figures. The text extraction had scrambled row labels, but the page image resolves them.

Excerpt read: Page 159: 18th Circuit, Law > $50,000, jury: 17 cases; 51.4 months. Page 163 note: Cook County did not report time lapse of all cases closed by jury or bench trial in 2023.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0113: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 6, Part V.C ¶4.

Authority type: case; as written: Langenhorst v. Norfolk Southern.pdf, p.12; pincite: p.12.

Cited for: Court congestion is relatively insignificant absent proof the other forum is faster

Quotes: ['is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Quotation is accurate (Langenhorst quoting Guerine, 198 Ill. 2d at 517) but is on attachment p.11, not p.12.

Excerpt read: Supplied Langenhorst opinion PDF p.11: 'Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0114: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 6, Part V.C ¶4.

Authority type: case; as written: see also First Am Bank v. Guerine.pdf, p.8, ¶3; pincite: p.8 ¶3.

Cited for: Court congestion alone is not dispositive

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Guerine p.8 so states.

Excerpt read: Supplied Guerine opinion PDF p.8: 'although the Cook County circuit court is more congested than either Kane or De Kalb County circuit courts, court congestion alone is not dispositive.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0115: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555, 652 N.E.2d 1228 (1st Dist. 1995)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: Defendants Motion to Transfer.pdf, PDF page 6, Part VI.

Authority type: case; as written: Bradbury v. St. Marys Hospital.pdf, p.3, ¶4; p.5, ¶1; pincite: p.3 ¶4; p.5 ¶1.

Cited for: "The Bradbury court reversed course only after observing" an unverified, unsupported motion

Quotes: ['quite remarkable, not for what it contains, but rather, for what it does not contain', 'unsupported and unverified assertions.']

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

The quotations are accurate (p.3 'quite remarkable ...'; p.5 'unsupported and unverified assertions'), but Bradbury did not 'reverse course': it AFFIRMED the trial court's denial of transfer because defendants failed to carry their evidentiary burden. The motion misstates the disposition.

Excerpt read: Supplied Bradbury opinion PDF p.3: 'The record in this case is quite remarkable, not for what it contains, but rather, for what it does not contain.' Supplied Bradbury opinion PDF p.5: 'other than the unsupported and unverified assertions of the defendants ... Accordingly, we affirm the order of the circuit court denying the defendants' motion'

- https://www.courtlistener.com/opinion/2065674/bradbury-v-st-marys-hospital-of-kankakee/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: MISCHARACTERIZED

The motion says the Bradbury court 'reversed course only after' seeing an unsupported motion. Bradbury initially denied leave to appeal, then heard the merits on Supreme Court remand, and ultimately affirmed the trial court's denial of transfer. It never changed course to grant transfer; the accurate quoted evidentiary criticisms do not support the motion's disposition phrasing.

Excerpt read: Bradbury attachment PDF p.1 recounts denial of leave and Supreme Court remand; p.5 affirms the circuit court order denying defendants' forum-non-conveniens motion.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Defendants%20Motion%20to%20Transfer.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0116: Davis v. Smith, No. 2025 L 5841 (scenario case)

Document: Davis Complaint.docx (attachment, assignments 1-2); location: Davis Complaint.docx, caption (DOCX, original pagination not retained).

Authority type: case; as written: Sara Davis v. John Smith, M.D., et al., No. 2025 L 5841 (Cir. Ct. Cook County); pincite: .

Cited for: Scenario case caption

Quotes: []

Context: 

Fictional by design: True; Fictional scenario lawsuit and docket number.

### First check: excluded by design


### Second check: not required


## FNC-0117: Scenario order appointing special administrator

Document: Davis Complaint.docx (attachment, assignments 1-2); location: Davis Complaint.docx, ¶2.

Authority type: other; as written: order of the Circuit Court of Cook County, Illinois, in Case No. [blank]; pincite: .

Cited for: Appointment of special administrator

Quotes: []

Context: 

Fictional by design: True; Fictional scenario appointment order (case number left blank).

### First check: excluded by design


### Second check: not required


## FNC-0118: Wrongful Death Act, 740 ILCS 180/0.01 et seq.

Document: Davis Complaint.docx (attachment, assignments 1-2); location: Davis Complaint.docx, ¶4.

Authority type: statute; as written: Illinois Wrongful Death Act, 740 ILCS 180/1 et seq.; pincite: .

Cited for: Basis for representative wrongful-death claims

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Statute exists and supplies the wrongful-death action pleaded.

Excerpt read: 740 ILCS 180/0.01: 'This Act may be cited as the Wrongful Death Act.'; 180/1: 'Whenever the death of a person shall be caused by wrongful act, neglect or default ...'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/074001800K1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/074001800K0.01.htm

### Second check: not required


## FNC-0119: Survival Act, 755 ILCS 5/27-6

Document: Davis Complaint.docx (attachment, assignments 1-2); location: Davis Complaint.docx, ¶4.

Authority type: statute; as written: Illinois Survival Act, 755 ILCS 5/27-6; pincite: .

Cited for: Basis for survival claims

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Section 27-6 of the Probate Act (commonly called the Survival Act) provides that actions for injury to the person survive.

Excerpt read: 'In addition to the actions which survive by the common law, the following also survive: ... actions to recover damages ... for an injury to the person (except slander and libel)'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/075500050K27-6.htm

### Second check: not required


## FNC-0120: 735 ILCS 5/2-622 (healing art malpractice affidavit and report)

Document: Davis Complaint.docx (attachment, assignments 1-2); location: Davis Complaint.docx, heading of Reviewing Physician's Written Report.

Authority type: statute; as written: Reviewing Physician's Written Report pursuant to 735 ILCS 5/2-622; pincite: .

Cited for: Healing-art malpractice certificate/report

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 'the reviewing health professional has determined in a written report ... that there is a reasonable and meritorious cause for the filing of such action'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073500050K2-622.htm

### Second check: not required


## FNC-0121: 735 ILCS 5/2-104 (wrong venue; motion to transfer)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 1.

Authority type: statute; as written: 735 ILCS 5/2-104; pincite: .

Cited for: Mary's Hospital of Kankakee, filed a motion to transfer venue to the circuit court of the 21st Judicial Circuit, Kankakee County, Illinois, pursuant to section 2-104 of the Code of Civil Procedure (Code) (

Quotes: []

Context: transfer venue to the circuit court of the 21st Judicial Circuit, Kankakee County, Illinois, pursuant to section 2-104 of the Code of Civil Procedure (Code) ( 735 ILCS 5/2-104 (West 1992)), alleging that venue was improperly fixed in Cook County. All of t

Fictional by design: False; 

### First check: VERIFIED

Current ILGA text read; the cited 1992 West edition was not read, but the provision's subject (transfer for improper venue) is unchanged in substance.

Excerpt read: 'No action shall abate or be dismissed because commenced in the wrong venue if there is a proper venue to which the cause may be transferred.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073500050K2-104.htm

### Second check: not required


## FNC-0122: Ill. S. Ct. R. 306(a)(1)(ii) (1990 numbering)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 1.

Authority type: court_rule; as written: Supreme Court Rules 306(a)(1)(ii) (134 Ill. 2d Rules 306(a)(1)(ii)); pincite: .

Cited for: Mary's Hospital filed a petition pursuant to Supreme Court Rule 306(a)(4), and the other defendants filed pursuant to Supreme Court Rules 306(a)(1)(ii) and (a)(1)(iv) (

Quotes: []

Context: ospital filed a petition pursuant to Supreme Court Rule 306(a)(4), and the other defendants filed pursuant to Supreme Court Rules 306(a)(1)(ii) and (a)(1)(iv) (134 Ill. 2d Rules 306(a)(1)(ii), (a)(1)(iv)). We denied both petitions, and the defendants filed petiti

Fictional by design: False; 

### First check: VERIFIED

Historical numbering: in the 1980s-1990s Rule 306(a)(1)(ii) covered forum non conveniens orders, as contemporaneous Illinois Supreme Court text (Moore) confirms; the current rule renumbers it as 306(a)(2).

Excerpt read: Moore (1983), read on CourtListener: 'Pursuant to Supreme Court Rule 306(a)(1)(ii) (87 Ill. 2d R. 306(a)(l)(ii)), each defendant sought review of the trial court's ruling' on forum non conveniens.

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0123: Ill. S. Ct. R. 306(a)(1)(iv) (1990 numbering)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 1.

Authority type: court_rule; as written: Supreme Court Rule 306(a)(1)(iv) (134 Ill. 2d Rules 306(a)(1)(iv)); pincite: .

Cited for: Mary's Hospital filed a petition pursuant to Supreme Court Rule 306(a)(4), and the other defendants filed pursuant to Supreme Court Rules 306(a)(1)(ii) and (a)(1)(iv) (

Quotes: []

Context: ospital filed a petition pursuant to Supreme Court Rule 306(a)(4), and the other defendants filed pursuant to Supreme Court Rules 306(a)(1)(ii) and (a)(1)(iv) (134 Ill. 2d Rules 306(a)(1)(ii), (a)(1)(iv)). We denied both petitions, and the defendants filed petiti

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The 134 Ill. 2d pre-1994 version of Rule 306(a)(1)(iv) was quoted in contemporaneous judicial text as covering residence-based venue appeals, and Bradbury says defendants invoked it after the February 1994 ruling. The official 2020 Rule 306 order records an amendment effective February 1, 1994, while later rule text uses Rule 306(a)(4). I could not read the signed 1993 amendment or an authenticated February 1994 rule compilation; the exact historical numbering operative at the Bradbury petition remains unresolved.

Excerpt read: McLane (1989) judicial text: Rule 306(a)(1)(iv) permitted review of orders granting or denying residence-based transfer of venue. Bradbury (1995) reports petitions under both (a)(1)(iv) and (a)(4).

- https://www.illinoiscourts.gov/resources/e1bf857c-ae6d-446c-b5d3-e01583b83878/093020.pdf
- https://law.justia.com/cases/illinois/supreme-court/1989/66019-7.html
- https://law.justia.com/cases/illinois/appellate-court/1993/252-ill-app-3d-632.html
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf

### Second check: not required


## FNC-0124: Ill. S. Ct. R. 315

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 1.

Authority type: court_rule; as written: Supreme Court Rule 315 (134 Ill. 2d R. 315); pincite: .

Cited for: We denied both petitions, and the defendants filed petitions for leave to appeal to the supreme court pursuant to Supreme Court Rule 315 (

Quotes: []

Context: (1)(ii), (a)(1)(iv)). We denied both petitions, and the defendants filed petitions for leave to appeal to the supreme court pursuant to Supreme Court Rule 315 (134 Ill. 2d R. 315). On February 1, 1995, the supreme court granted the defendants' petitions and,

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage. Cited as the 134 Ill. 2d edition; that edition was not read.

Excerpt read: 'Rule 315. Leave to Appeal From the Appellate Court to the Supreme Court'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0125: 735 ILCS 5/2-101 (venue)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 1.

Authority type: statute; as written: 735 ILCS 5/2-101; pincite: .

Cited for:  with probable cause for the purpose of obtaining a judgment against him or her and not solely for the purpose of fixing venue in that county, or (2) in the county in which the transaction or some part thereof occurred out of which the cause of action arose."

Quotes: []

Context: he purpose of fixing venue in that county, or (2) in the county in which the transaction or some part thereof occurred out of which the cause of action arose." 735 ILCS 5/2-101 (West 1992).

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session. (The opinion cites an earlier West edition; current text read, provision unchanged in substance.)

Excerpt read: 'every action must be commenced (1) in the county of residence of any defendant who is joined in good faith ... or (2) in the county in which the transaction or some part thereof occurred out of which the cause of action arose.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073500050K2-101.htm

### Second check: not required


## FNC-0126: Wrongful Death Act, 740 ILCS 180/0.01 et seq.

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: statute; as written: 740 ILCS 180/0.01; pincite: .

Cited for: Mary's Hospital even goes so far as to contend that death is not an element of a cause of action for wrongful death. We disagree. The Wrongful Death Act (

Quotes: []

Context: St. Mary's Hospital even goes so far as to contend that death is not an element of a cause of action for wrongful death. We disagree. The Wrongful Death Act ( 740 ILCS 180/0.01 et seq. (West 1992)) provides a remedy to the surviving spouse and next of kin

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session. (The opinion cites an earlier West edition; current text read, provision unchanged in substance.)

Excerpt read: 740 ILCS 180/0.01: 'This Act may be cited as the Wrongful Death Act.'; 180/1: 'Whenever the death of a person shall be caused by wrongful act, neglect or default ...'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/074001800K1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/074001800K0.01.htm

### Second check: not required


## FNC-0127: Vaughn v. Granite City Steel Division of National Steel Corp., 217 Ill. App. 3d 46, 576 N.E.2d 874 (1991)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: case; as written: 217 Ill. App.3d 46; pincite: .

Cited for: While it is true that the action is premised upon the wrongful conduct of the defendant in breach of a duty owed to the decedent resulting in death (see Vaughn v. Granite City Steel Division of National Steel Corp. (1991),

Quotes: []

Context: conduct of the defendant in breach of a duty owed to the decedent resulting in death (see Vaughn v. Granite City Steel Division of National Steel Corp. (1991), 217 Ill. App.3d 46, 576 N.E.2d 874), the Wrongful Death Act does not provide for the survival of a

Fictional by design: False; 

### First check: VERIFIED

Vaughn read on CourtListener; a Wrongful Death Act case resting on a duty owed to the decedent.

Excerpt read: 'We have previously discussed the fact that defendant did, in fact, owe a duty to decedent ...'; wrongful death action under the Act

- https://www.courtlistener.com/opinion/2013179/vaughn-v-granite-city-steel-division-of-national-steel-corp/

### Second check: not required


## FNC-0128: Wyness v. Armstrong World Industries, Inc., 131 Ill. 2d 403, 546 N.E.2d 568 (1989)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: case; as written: 131 Ill.2d 403; pincite: .

Cited for: The Wrongful Death Act governs the right of the persons designated by the statute to recover for their own pecuniary injuries suffered as a consequence of the death of the decedent. ( Wyness v. Armstrong World Industries, Inc. (1989),

Quotes: []

Context: tatute to recover for their own pecuniary injuries suffered as a consequence of the death of the decedent. ( Wyness v. Armstrong World Industries, Inc. (1989), 131 Ill.2d 403, 546 N.E.2d 568.) Consequently, the action accrues upon the decedent's death an

Fictional by design: False; 

### First check: VERIFIED

Wyness passage read on CourtListener.

Excerpt read: 'The wrongful death action allows, in contrast, the next of kin to recover damages for their own loss based on the wrongful actions of another.'

- https://www.courtlistener.com/opinion/2239981/wyness-v-armstrong-world-industries-inc/

### Second check: not required


## FNC-0129: Dettman-Brunsfeld v. Szanto, 267 Ill. App. 3d 1050, 642 N.E.2d 809 (1994)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: case; as written: 267 Ill. App.3d 1050; pincite: .

Cited for: (1989), 131 Ill.2d 403, 546 N.E.2d 568.) Consequently, the action accrues upon the decedent's death and provides a remedy for damages incurred as a result of the death itself. ( Dettman-Brunsfeld v. Szanto (1994),

Quotes: []

Context: the action accrues upon the decedent's death and provides a remedy for damages incurred as a result of the death itself. ( Dettman-Brunsfeld v. Szanto (1994), 267 Ill. App.3d 1050, 642 N.E.2d 809.) Not only is death an element of such an action, it is the las

Fictional by design: False; 

### First check: VERIFIED

Dettman-Brunsfeld passage read on CourtListener.

Excerpt read: 'The damages for a wrongful death action do not accrue until after the death of the injured person and address the injury suffered by the next of kin due to the loss of the decedent.'

- https://www.courtlistener.com/opinion/2103606/dettman-brunsfeld-v-szanto/

### Second check: not required


## FNC-0130: Gray v. American Radiator & Standard Sanitary Corp., 22 Ill. 2d 432, 176 N.E.2d 761 (1961)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: case; as written: 22 Ill.2d 432; pincite: .

Cited for: Albeit in the context of a jurisdictional discussion, our supreme court has held that the place of a wrong is where the last event takes place which is necessary to render the actor liable. ( Gray v. American Radiator Standard Sanitary Corp. (1961),

Quotes: []

Context: place of a wrong is where the last event takes place which is necessary to render the actor liable. ( Gray v. American Radiator Standard Sanitary Corp. (1961), 22 Ill.2d 432, 176 N.E.2d 761.) In a wrongful death action, that place is the place of the de

Fictional by design: False; 

### First check: VERIFIED

Gray passage read on CourtListener.

Excerpt read: 'It is well established, however, that in law the place of a wrong is where the last event takes place which is necessary to render the actor liable.'

- https://www.courtlistener.com/opinion/2122492/gray-v-american-radiator-standard-sanitary-corp/

### Second check: not required


## FNC-0131: Moore v. Chicago & North Western Transportation Co., 99 Ill. 2d 73, 457 N.E.2d 417 (1983)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: case; as written: 99 Ill.2d 73; pincite: .

Cited for: of the doctrine of forum non conveniens presupposes the existence of more than one proper venue within the State and focuses the inquiry upon the relative convenience of the plaintiff's chosen venue. ( Moore v. Chicago North Western Transportation Co. (1983),

Quotes: []

Context: in the State and focuses the inquiry upon the relative convenience of the plaintiff's chosen venue. ( Moore v. Chicago North Western Transportation Co. (1983), 99 Ill.2d 73, 457 N.E.2d 417.) The resolution of a forum non conveniens motion requires the

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Moore (an interstate dismissal case) states: 'Implicit in the doctrine of forum non conveniens is the existence of at least two forums in which the controversy may be litigated ... The inquiry therefore focuses upon the relative convenience of the available forums.' Bradbury adapts this to intrastate venue; fair but loose paraphrase.

Excerpt read: Moore (CourtListener 2076615): 'Implicit in the doctrine of forum non conveniens is the existence of at least two forums in which the controversy may be litigated. ... The inquiry therefore focuses upon the relative convenience of the available forums.'

- https://www.courtlistener.com/opinion/2076615/moore-v-chicago-north-western-transportation-co/

### Second check: not required


## FNC-0132: Boner v. Peabody Coal Co., 142 Ill. 2d 523, 568 N.E.2d 883 (1991)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: case; as written: 142 Ill.2d 523; pincite: .

Cited for: n conveniens motion requires the court to apply an uneven balancing test to various private interest factors affecting the convenience of the litigants and public interest factors affecting the administration of the courts. ( Boner v. Peabody Coal Co. (1991),

Quotes: []

Context: factors affecting the convenience of the litigants and public interest factors affecting the administration of the courts. ( Boner v. Peabody Coal Co. (1991), 142 Ill.2d 523, 568 N.E.2d 883; Griffith v. Mitsubishi Aircraft International, Inc. (1990), 13

Fictional by design: False; 

### First check: VERIFIED

Boner text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'This court may not reach its decision by speculating on how many more witnesses from Gallatin County may be called to testify.'; 'While a circuit court may consider this factor, little weight should be accorded it.'

- https://www.courtlistener.com/opinion/2094308/boner-v-peabody-coal-co/

### Second check: not required


## FNC-0133: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: case; as written: 136 Ill.2d 101; pincite: .

Cited for: (1991), 142 Ill.2d 523, 568 N.E.2d 883; Griffith v. Mitsubishi Aircraft International, Inc. (1990),

Quotes: []

Context: e administration of the courts. ( Boner v. Peabody Coal Co. (1991), 142 Ill.2d 523, 568 N.E.2d 883; Griffith v. Mitsubishi Aircraft International, Inc. (1990), 136 Ill.2d 101, 554 N.E.2d 209; McClain v. Illinois Central Gulf R.R. Co. (1988), 121 Ill.2d 2

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'If the plaintiff is foreign to the forum selected, the forum choice should be given less deference ... The test, then, is whether the relevant factors, viewed in their totality, strongly favor transfer to the forum suggested by defendant.'

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0134: McClain v. Illinois Central Gulf R.R. Co., 121 Ill. 2d 278, 520 N.E.2d 368 (1988)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: case; as written: 121 Ill.2d 278; pincite: .

Cited for: (1990), 136 Ill.2d 101, 554 N.E.2d 209; McClain v. Illinois Central Gulf R.R. Co. (1988),

Quotes: []

Context: , 568 N.E.2d 883; Griffith v. Mitsubishi Aircraft International, Inc. (1990), 136 Ill.2d 101, 554 N.E.2d 209; McClain v. Illinois Central Gulf R.R. Co. (1988), 121 Ill.2d 278, 520 N.E.2d 368; Bland v. Norfolk Western Ry. Co. (1987), 116 Ill.2d 217, 506 N

Fictional by design: False; 

### First check: VERIFIED

McClain passage read on CourtListener.

Excerpt read: 'if the chosen forum is the plaintiff's home forum, that choice will be given substantial deference; otherwise the deference to the plaintiff's choice is considerably lessened.'

- https://www.courtlistener.com/opinion/2076555/mcclain-v-illinois-central-gulf-railroad/

### Second check: not required


## FNC-0135: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217, 506 N.E.2d 1291 (1987)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: case; as written: 116 Ill.2d 217; pincite: .

Cited for: (1988), 121 Ill.2d 278, 520 N.E.2d 368; Bland v. Norfolk Western Ry. Co. (1987),

Quotes: []

Context: 90), 136 Ill.2d 101, 554 N.E.2d 209; McClain v. Illinois Central Gulf R.R. Co. (1988), 121 Ill.2d 278, 520 N.E.2d 368; Bland v. Norfolk Western Ry. Co. (1987), 116 Ill.2d 217, 506 N.E.2d 1291.) To justify the granting of a forum non conveniens motion, th

Fictional by design: False; 

### First check: VERIFIED

Bland text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'One should be cautious, however, not to give undue weight to the fact that a plaintiff's treating physician or expert has an office in the plaintiff's chosen forum. To do so would allow a plaintiff to easily frustrate the forum non conveniens principle ...'

- https://www.courtlistener.com/opinion/2210166/bland-v-norfolk-western-railway-co/

### Second check: not required


## FNC-0136: Boner v. Peabody Coal Co., 142 Ill. 2d 523, 568 N.E.2d 883 (1991)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: case; as written: 142 Ill.2d 523; pincite: .

Cited for:  116 Ill.2d 217, 506 N.E.2d 1291.) To justify the granting of a forum non conveniens motion, the defendant must meet its burden of establishing that the relevant factors for consideration, viewed in their totality, strongly favor the suggested forum. ( Boner,

Quotes: []

Context: endant must meet its burden of establishing that the relevant factors for consideration, viewed in their totality, strongly favor the suggested forum. ( Boner, 142 Ill.2d 523, 568 N.E.2d 883.) Whether to grant or deny such a motion is a matter committed

Fictional by design: False; 

### First check: VERIFIED

Boner text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'This court may not reach its decision by speculating on how many more witnesses from Gallatin County may be called to testify.'; 'While a circuit court may consider this factor, little weight should be accorded it.'

- https://www.courtlistener.com/opinion/2094308/boner-v-peabody-coal-co/

### Second check: not required


## FNC-0137: Washington v. Illinois Power Co., 144 Ill. 2d 395, 581 N.E.2d 644 (1991)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 3.

Authority type: case; as written: 144 Ill.2d 395; pincite: .

Cited for:  the trial court, the exercise of which will not be disturbed on appeal absent a clear abuse. Washington v. Illinois Power Co. (1991),

Quotes: []

Context: the trial court, the exercise of which will not be disturbed on appeal absent a clear abuse. Washington v. Illinois Power Co. (1991), 144 Ill.2d 395, 581 N.E.2d 644. Our supreme court has identified the relevant private and publ

Fictional by design: False; 

### First check: VERIFIED

Washington passages read on CourtListener.

Excerpt read: 'The trial court's decision will be reversed on review only upon showing that, in deciding as it did, the court clearly abused that discretion.'; 'This court has found the annual report of the Administrative Office of the Illinois Courts to be a proper source of reference in assessing court congestion.'

- https://www.courtlistener.com/opinion/2171002/washington-v-illinois-power-co/

### Second check: not required


## FNC-0138: Boner v. Peabody Coal Co., 142 Ill. 2d 523, 568 N.E.2d 883 (1991)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 3.

Authority type: case; as written: 142 Ill.2d 523; pincite: .

Cited for: esses, the cost of obtaining the attendance of willing witnesses, the possibility of the jury viewing the premises, practical problems that make the trial of a case easy, expeditious, and inexpensive, and the advantages and obstacles to a fair trial. ( Boner,

Quotes: []

Context: g the premises, practical problems that make the trial of a case easy, expeditious, and inexpensive, and the advantages and obstacles to a fair trial. ( Boner, 142 Ill.2d 523, 568 N.E.2d 883; Griffith, 136 Ill.2d 101, 554 N.E.2d 209; Bland, 116 Ill.2d 21

Fictional by design: False; 

### First check: VERIFIED

Boner text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'This court may not reach its decision by speculating on how many more witnesses from Gallatin County may be called to testify.'; 'While a circuit court may consider this factor, little weight should be accorded it.'

- https://www.courtlistener.com/opinion/2094308/boner-v-peabody-coal-co/

### Second check: not required


## FNC-0139: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 3.

Authority type: case; as written: 136 Ill.2d 101; pincite: .

Cited for: e of willing witnesses, the possibility of the jury viewing the premises, practical problems that make the trial of a case easy, expeditious, and inexpensive, and the advantages and obstacles to a fair trial. ( Boner, 142 Ill.2d 523, 568 N.E.2d 883; Griffith,

Quotes: []

Context: ke the trial of a case easy, expeditious, and inexpensive, and the advantages and obstacles to a fair trial. ( Boner, 142 Ill.2d 523, 568 N.E.2d 883; Griffith, 136 Ill.2d 101, 554 N.E.2d 209; Bland, 116 Ill.2d 217, 506 N.E.2d 1291.) The public interest f

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'If the plaintiff is foreign to the forum selected, the forum choice should be given less deference ... The test, then, is whether the relevant factors, viewed in their totality, strongly favor transfer to the forum suggested by defendant.'

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0140: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217, 506 N.E.2d 1291 (1987)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 3.

Authority type: case; as written: 116 Ill.2d 217; pincite: .

Cited for: ( Boner, 142 Ill.2d 523, 568 N.E.2d 883; Griffith, 136 Ill.2d 101, 554 N.E.2d 209; Bland,

Quotes: []

Context: s, and inexpensive, and the advantages and obstacles to a fair trial. ( Boner, 142 Ill.2d 523, 568 N.E.2d 883; Griffith, 136 Ill.2d 101, 554 N.E.2d 209; Bland, 116 Ill.2d 217, 506 N.E.2d 1291.) The public interest factors include the administrative diffi

Fictional by design: False; 

### First check: VERIFIED

Bland text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'One should be cautious, however, not to give undue weight to the fact that a plaintiff's treating physician or expert has an office in the plaintiff's chosen forum. To do so would allow a plaintiff to easily frustrate the forum non conveniens principle ...'

- https://www.courtlistener.com/opinion/2210166/bland-v-norfolk-western-railway-co/

### Second check: not required


## FNC-0141: Boner v. Peabody Coal Co., 142 Ill. 2d 523, 568 N.E.2d 883 (1991)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 3.

Authority type: case; as written: 142 Ill.2d 523; pincite: .

Cited for:  the local interest in having localized controversies decided at home which requires a consideration of the situs of the injury, the protection of finite judicial resources, and the unfairness of burdening citizens in an unrelated forum with jury duty. Boner,

Quotes: []

Context: of the situs of the injury, the protection of finite judicial resources, and the unfairness of burdening citizens in an unrelated forum with jury duty. Boner, 142 Ill.2d 523, 568 N.E.2d 883; Griffith, 136 Ill.2d 101, 554 N.E.2d 209; Bland, 116 Ill.2d 21

Fictional by design: False; 

### First check: VERIFIED

Boner text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'This court may not reach its decision by speculating on how many more witnesses from Gallatin County may be called to testify.'; 'While a circuit court may consider this factor, little weight should be accorded it.'

- https://www.courtlistener.com/opinion/2094308/boner-v-peabody-coal-co/

### Second check: not required


## FNC-0142: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 3.

Authority type: case; as written: 136 Ill.2d 101; pincite: .

Cited for: ntroversies decided at home which requires a consideration of the situs of the injury, the protection of finite judicial resources, and the unfairness of burdening citizens in an unrelated forum with jury duty. Boner, 142 Ill.2d 523, 568 N.E.2d 883; Griffith,

Quotes: []

Context: n of finite judicial resources, and the unfairness of burdening citizens in an unrelated forum with jury duty. Boner, 142 Ill.2d 523, 568 N.E.2d 883; Griffith, 136 Ill.2d 101, 554 N.E.2d 209; Bland, 116 Ill.2d 217, 506 N.E.2d 1291. After balancing the pr

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'If the plaintiff is foreign to the forum selected, the forum choice should be given less deference ... The test, then, is whether the relevant factors, viewed in their totality, strongly favor transfer to the forum suggested by defendant.'

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0143: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217, 506 N.E.2d 1291 (1987)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 3.

Authority type: case; as written: 116 Ill.2d 217; pincite: .

Cited for: Boner, 142 Ill.2d 523, 568 N.E.2d 883; Griffith, 136 Ill.2d 101, 554 N.E.2d 209; Bland,

Quotes: []

Context: unfairness of burdening citizens in an unrelated forum with jury duty. Boner, 142 Ill.2d 523, 568 N.E.2d 883; Griffith, 136 Ill.2d 101, 554 N.E.2d 209; Bland, 116 Ill.2d 217, 506 N.E.2d 1291. After balancing the private and public interests at issue, a

Fictional by design: False; 

### First check: VERIFIED

Bland text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'One should be cautious, however, not to give undue weight to the fact that a plaintiff's treating physician or expert has an office in the plaintiff's chosen forum. To do so would allow a plaintiff to easily frustrate the forum non conveniens principle ...'

- https://www.courtlistener.com/opinion/2210166/bland-v-norfolk-western-railway-co/

### Second check: not required


## FNC-0144: McClain v. Illinois Central Gulf R.R. Co., 121 Ill. 2d 278, 520 N.E.2d 368 (1988)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 3.

Authority type: case; as written: 121 Ill.2d 278; pincite: .

Cited for: When a plaintiff chooses her home forum, that choice is to be accorded substantial deference. ( McClain,

Quotes: []

Context: her the plaintiff is a resident of the selected forum. When a plaintiff chooses her home forum, that choice is to be accorded substantial deference. ( McClain, 121 Ill.2d 278, 520 N.E.2d 368.) If the plaintiff is foreign to the selected forum, her choice

Fictional by design: False; 

### First check: VERIFIED

McClain passage read on CourtListener.

Excerpt read: 'if the chosen forum is the plaintiff's home forum, that choice will be given substantial deference; otherwise the deference to the plaintiff's choice is considerably lessened.'

- https://www.courtlistener.com/opinion/2076555/mcclain-v-illinois-central-gulf-railroad/

### Second check: not required


## FNC-0145: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 3.

Authority type: case; as written: 136 Ill.2d 101; pincite: .

Cited for: ( McClain, 121 Ill.2d 278, 520 N.E.2d 368.) If the plaintiff is foreign to the selected forum, her choice is given less deference. ( Griffith,

Quotes: []

Context: ntial deference. ( McClain, 121 Ill.2d 278, 520 N.E.2d 368.) If the plaintiff is foreign to the selected forum, her choice is given less deference. ( Griffith, 136 Ill.2d 101, 554 N.E.2d 209.) In a wrongful death action, it is the decedent's residence at

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'If the plaintiff is foreign to the forum selected, the forum choice should be given less deference ... The test, then, is whether the relevant factors, viewed in their totality, strongly favor transfer to the forum suggested by defendant.'

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0146: Moore v. Chicago & North Western Transportation Co., 99 Ill. 2d 73, 457 N.E.2d 417 (1983)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 3.

Authority type: case; as written: 99 Ill.2d 73; pincite: .

Cited for: ( Griffith, 136 Ill.2d 101, 554 N.E.2d 209.) In a wrongful death action, it is the decedent's residence at the time of death that is of significance. Moore,

Quotes: []

Context: e. ( Griffith, 136 Ill.2d 101, 554 N.E.2d 209.) In a wrongful death action, it is the decedent's residence at the time of death that is of significance. Moore, 99 Ill.2d 73, 457 N.E.2d 417. The record in this case is quite remarkable, not for what it c

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Moore treats the administrator-plaintiff's residence as of 'minimal significance' because he sued only in a representative capacity, with the decedent a Wisconsin resident; it does not state the rule in Bradbury's terms ('it is the decedent's residence at the time of death that is of significance'). Supportive in substance, loosely characterized.

Excerpt read: Moore: 'In light of the representative capacity in which plaintiff here acts, his residency has no relationship to the litigation except as a nominal party. Thus, under the facts of this case, plaintiff's choice of Cook County, Illinois, is of minimal significance.'

- https://www.courtlistener.com/opinion/2076615/moore-v-chicago-north-western-transportation-co/

### Second check: not required


## FNC-0147: Ill. S. Ct. R. 237

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 4.

Authority type: court_rule; as written: Supreme Court Rule 237 (134 Ill. 2d R. 237); pincite: .

Cited for: t it appears medical records relative to the decedent are located in both Cook and Kankakee Counties and that process would be available in either county to compel the attendance of any unwilling Illinois resident witnesses pursuant to Supreme Court Rule 237 (

Quotes: []

Context: and that process would be available in either county to compel the attendance of any unwilling Illinois resident witnesses pursuant to Supreme Court Rule 237 (134 Ill. 2d R. 237). Other than the obvious convenience to the defendants if they were to defend t

Fictional by design: False; 

### First check: VERIFIED

Current compiled rule read; the 1990 (134 Ill. 2d R. 237) and later versions cited were not separately read, but the rule's subject (compelling witnesses' attendance at trial) is unchanged. Cited as the 134 Ill. 2d edition; that edition was not read.

Excerpt read: 'Rule 237. Compelling Appearances of Witnesses at Trial. (a) Service of Subpoenas. Any witness shall respond to any lawful subpoena ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0148: Boner v. Peabody Coal Co., 142 Ill. 2d 523, 568 N.E.2d 883 (1991)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 4.

Authority type: case; as written: 142 Ill. 2d at 533; pincite: 533.

Cited for: Neither this court nor the trial court should be forced to reach a decision by speculating as to the identity, number, and location of witnesses that a party might call to testify. See Boner,

Quotes: []

Context: court should be forced to reach a decision by speculating as to the identity, number, and location of witnesses that a party might call to testify. See Boner, 142 Ill. 2d at 533. The defendants argue that little weight should be accorded to the plaintiff's

Fictional by design: False; 

### First check: VERIFIED

Boner text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Boner, 142 Ill. 2d at 533: 'This court may not reach its decision by speculating on how many more witnesses from Gallatin County may be called to testify.'

- https://www.courtlistener.com/opinion/2094308/boner-v-peabody-coal-co/

### Second check: not required


## FNC-0149: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217, 506 N.E.2d 1291 (1987)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 4.

Authority type: case; as written: 116 Ill. 2d at 227; pincite: 227.

Cited for: The defendants argue that little weight should be accorded to the plaintiff's identification of 13 health care professionals from the University of Chicago Hospital as potential trial witnesses. They support this argument by citing to Bland (

Quotes: []

Context: tification of 13 health care professionals from the University of Chicago Hospital as potential trial witnesses. They support this argument by citing to Bland (116 Ill. 2d at 227), which held that plaintiffs should not be allowed to frustrate the forum non c

Fictional by design: False; 

### First check: VERIFIED

Bland text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Bland, 116 Ill. 2d at 227: 'To do so would allow a plaintiff to easily frustrate the forum non conveniens principle by selecting as a witness a treating physician or expert in what would, in reality, be an inconvenient forum.'

- https://www.courtlistener.com/opinion/2210166/bland-v-norfolk-western-railway-co/

### Second check: not required


## FNC-0150: Washington v. Illinois Power Co., 144 Ill. 2d 395, 581 N.E.2d 644 (1991)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 4.

Authority type: case; as written: 144 Ill.2d 395; pincite: .

Cited for: Also, while the defendants are correct that judicial notice may be taken of the statistics issued by the Director of the Administrative Office of the Illinois Courts in assessing court congestion ( Washington,

Quotes: []

Context: al notice may be taken of the statistics issued by the Director of the Administrative Office of the Illinois Courts in assessing court congestion ( Washington, 144 Ill.2d 395, 581 N.E.2d 644), we note that the defendants never requested that the trial co

Fictional by design: False; 

### First check: VERIFIED

Washington passages read on CourtListener.

Excerpt read: 'The trial court's decision will be reversed on review only upon showing that, in deciding as it did, the court clearly abused that discretion.'; 'This court has found the annual report of the Administrative Office of the Illinois Courts to be a proper source of reference in assessing court congestion.'

- https://www.courtlistener.com/opinion/2171002/washington-v-illinois-power-co/

### Second check: not required


## FNC-0151: Golden Rule Insurance Co. v. Manasherov, 200 Ill. App. 3d 961, 558 N.E.2d 543 (1990)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 4.

Authority type: case; as written: 200 Ill. App.3d 961; pincite: .

Cited for: Ill.2d 395, 581 N.E.2d 644), we note that the defendants never requested that the trial court take notice of those statistics and never quoted any such statistics to either the trial court or to this court. (See Golden Rule Insurance Co. v. Manasherov (1990),

Quotes: []

Context: otice of those statistics and never quoted any such statistics to either the trial court or to this court. (See Golden Rule Insurance Co. v. Manasherov (1990), 200 Ill. App.3d 961, 558 N.E.2d 543.) Absent the parties' reliance upon the statistics issued by th

Fictional by design: False; 

### First check: VERIFIED

Golden Rule passage read on CourtListener.

Excerpt read: 'While we agree with plaintiff that a court may properly take notice of court congestion ..., the record reveals that the plaintiff did not ask the trial court to take judicial notice of the Annual Report ...'

- https://www.courtlistener.com/opinion/2234606/golden-rule-insurance-v-manasherov/

### Second check: not required


## FNC-0152: Hoffmeister v. K mart Corp., 181 Ill. App. 3d 739, 537 N.E.2d 460 (1989)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 4.

Authority type: case; as written: 181 Ill. App.3d 739; pincite: .

Cited for: ) Absent the parties' reliance upon the statistics issued by the Administrative Office, the trial court is in a much better position than we are to assess the burden on its own docket that the trial of this case might pose. Hoffmeister v. K mart Corp. (1989),

Quotes: []

Context: urt is in a much better position than we are to assess the burden on its own docket that the trial of this case might pose. Hoffmeister v. K mart Corp. (1989), 181 Ill. App.3d 739, 537 N.E.2d 460. Lastly, and most importantly, we do not know the residence of

Fictional by design: False; 

### First check: VERIFIED

Hoffmeister passage read on CourtListener.

Excerpt read: 'The trial court was in a better position than this court to assess the burden posed by its own docket, and we will not second-guess its judgment.'

- https://www.courtlistener.com/opinion/2077429/hoffmeister-v-k-mart-corp/

### Second check: not required


## FNC-0153: Ill. S. Ct. R. 306(a)(2)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 2.

Authority type: court_rule; as written: Supreme Court Rule 306(a (166 Ill.2d R. 306(a); pincite: .

Cited for: The plaintiffs chose Kane County, but filed an interlocutory appeal under Supreme Court Rule 306(a)(2) (

Quotes: []

Context: ccurred, or Kane County, where the Malone family lives. The plaintiffs chose Kane County, but filed an interlocutory appeal under Supreme Court Rule 306(a)(2) (166 Ill.2d R. 306(a)(2)). The appellate court denied the plaintiffs' petition for leave to appeal,

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage.

Excerpt read: '(2) from an order of the circuit court allowing or denying a motion to dismiss on the grounds of forum non conveniens, or ... a motion to transfer a case to another county within this State on such grounds'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0154: Ill. S. Ct. R. 315

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 2.

Authority type: court_rule; as written: Supreme Court Rule 315 (177 Ill.2d R. 315); pincite: .

Cited for: We granted the plaintiffs' subsequent petition for leave to appeal. See

Quotes: []

Context: ntiffs' petition for leave to appeal, and the plaintiffs sought review from this court. We granted the plaintiffs' subsequent petition for leave to appeal. See 177 Ill.2d R. 315. For the first time since Peile v. Skelgas, Inc., 163 Ill.2d 323, 206 Ill.Dec.

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage. Cited as the 177 Ill. 2d edition; that edition was not read.

Excerpt read: 'Rule 315. Leave to Appeal From the Appellate Court to the Supreme Court'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0155: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 2.

Authority type: case; as written: 163 Ill.2d 323; pincite: .

Cited for: See 177 Ill.2d R. 315. For the first time since Peile v. Skelgas, Inc.,

Quotes: []

Context: ew from this court. We granted the plaintiffs' subsequent petition for leave to appeal. See 177 Ill.2d R. 315. For the first time since Peile v. Skelgas, Inc., 163 Ill.2d 323, 206 Ill.Dec. 179, 645 N.E.2d 184 (1994), we are called upon to evaluate the co

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'In most instances, the plaintiff's initial choice of forum will prevail, provided venue is proper and the inconvenience factors attached to such forum do not greatly outweigh the plaintiff's substantial right to try the case in the chosen forum.'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0156: 735 ILCS 5/2-101 (venue)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 2.

Authority type: statute; as written: 735 ILCS 5/2-101; pincite: .

Cited for:  with probable cause for the purpose of obtaining a judgment against him or her and not solely for the purpose of fixing venue in that county, or (2) in the county in which the transaction or some part thereof occurred out of which the cause of action arose.”

Quotes: []

Context: he purpose of fixing venue in that county, or (2) in the county in which the transaction or some part thereof occurred out of which the cause of action arose.” 735 ILCS 5/2-101 (West 2000). Here, the plaintiffs filed their complaint in Cook County, where G

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session. (The opinion cites an earlier West edition; current text read, provision unchanged in substance.)

Excerpt read: 'every action must be commenced (1) in the county of residence of any defendant who is joined in good faith ... or (2) in the county in which the transaction or some part thereof occurred out of which the cause of action arose.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073500050K2-101.htm

### Second check: not required


## FNC-0157: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 2.

Authority type: case; as written: 163 Ill.2d at 336; pincite: 336.

Cited for: In ruling on a forum non conveniens motion, a trial court enjoys considerable discretion. Peile,

Quotes: []

Context: asserted, another venue is more appropriate than Cook County. In ruling on a forum non conveniens motion, a trial court enjoys considerable discretion. Peile, 163 Ill.2d at 336, 206 Ill.Dec. 179, 645 N.E.2d 184; see Fender v. St. Louis Southwestern Ry. Co.

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Peile, 163 Ill. 2d at 336: 'The trial court is vested with considerable discretion in its determination of whether transfer is warranted'; 'If, however, the litigation has no practical connection to the forum ... the court should grant the motion for transfer.'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0158: Fender v. St. Louis Southwestern Ry. Co., 49 Ill. 2d 1, 273 N.E.2d 353 (1971)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 2.

Authority type: case; as written: 49 Ill.2d 1, 4; pincite: 4.

Cited for: 179, 645 N.E.2d 184; see Fender v. St. Louis Southwestern Ry. Co.,

Quotes: []

Context: motion, a trial court enjoys considerable discretion. Peile, 163 Ill.2d at 336, 206 Ill.Dec. 179, 645 N.E.2d 184; see Fender v. St. Louis Southwestern Ry. Co., 49 Ill.2d 1, 4, 273 N.E.2d 353 (1971). Accordingly, the sole issue before us is whether the tr

Fictional by design: False; 

### First check: VERIFIED

Fender passage read on CourtListener.

Excerpt read: 'The discretion to be exercised in ruling on a forum non conveniens motion is that of the trial court.'

- https://www.courtlistener.com/opinion/2042124/fender-v-st-louis-southwestern-railway-co/

### Second check: not required


## FNC-0159: Adkins v. Chicago, Rock Island & Pacific R.R. Co., 54 Ill. 2d 511, 301 N.E.2d 729 (1973)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 2.

Authority type: case; as written: 54 Ill.2d 511, 514; pincite: 514.

Cited for: Forum non conveniens is an equitable doctrine “founded in considerations of fundamental fairness and sensible and effective judicial administration” (Adkins v. Chicago, Rock Island & Pacific R.R. Co.,

Quotes: []

Context: rine “founded in considerations of fundamental fairness and sensible and effective judicial administration” (Adkins v. Chicago, Rock Island & Pacific R.R. Co., 54 Ill.2d 511, 514, 301 N.E.2d 729 (1973)), which allows a trial court to decline jurisdiction in

Fictional by design: False; 

### First check: VERIFIED

Adkins passage read on CourtListener.

Excerpt read: 'Forum non conveniens is a doctrine that is founded in considerations of fundamental fairness and sensible and effective judicial administration.'

- https://www.courtlistener.com/opinion/2210722/adkins-v-chi-r-is-pac-rr-co/

### Second check: not required


## FNC-0160: Vinson v. Allstate, 144 Ill. 2d 306, 579 N.E.2d 857 (1991)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 2.

Authority type: case; as written: 144 Ill.2d 306, 310; pincite: 310.

Cited for: Co., 54 Ill.2d 511, 514, 301 N.E.2d 729 (1973)), which allows a trial court to decline jurisdiction in the exceptional case where trial in another forum with proper jurisdiction and venue “would better serve the ends of justice” (Vinson v. Allstate,

Quotes: []

Context: isdiction in the exceptional case where trial in another forum with proper jurisdiction and venue “would better serve the ends of justice” (Vinson v. Allstate, 144 Ill.2d 306, 310, 162 Ill.Dec. 43, 579 N.E.2d 857 (1991)). Although the forum non conveniens doc

Fictional by design: False; 

### First check: VERIFIED

Vinson passages read on CourtListener.

Excerpt read: 'a court ... may nevertheless decline jurisdiction of a case when it is apparent that trial in another forum ... would be more convenient and would better serve the ends of justice.'; 'the fact that Allstate conducts business within the county is not the only factor the court should consider in its analysis.'

- https://www.courtlistener.com/opinion/2238079/vinson-v-allstate/

### Second check: not required


## FNC-0161: Gulf Oil Corp. v. Gilbert, 330 U.S. 501 (1947)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 2.

Authority type: case; as written: 330 U.S. 501; pincite: .

Cited for: Although the forum non conveniens doctrine has a long history at common law, its general application crystalized following the United State Supreme Court's landmark decision in Gulf Oil Corp. v. Gilbert,

Quotes: []

Context: as a long history at common law, its general application crystalized following the United State Supreme Court's landmark decision in Gulf Oil Corp. v. Gilbert, 330 U.S. 501, 67 S.Ct. 839, 91 L.Ed. 1055 (1947). The Gulf Oil Court stated: “The principle

Fictional by design: False; 

### First check: VERIFIED

Gulf Oil passage read on CourtListener.

Excerpt read: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/104393/gulf-oil-corp-v-gilbert/

### Second check: not required


## FNC-0162: Gulf Oil Corp. v. Gilbert, 330 U.S. 501 (1947)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 3.

Authority type: case; as written: 330 U.S. at 507-08; pincite: 507-08.

Cited for: Jury duty is a burden that ought not to be imposed upon the people of a community which has no relation to the ligation.” (Emphasis added.) Gulf Oil,

Quotes: []

Context: s origin. Jury duty is a burden that ought not to be imposed upon the people of a community which has no relation to the ligation.” (Emphasis added.) Gulf Oil, 330 U.S. at 507-08, 67 S.Ct. at 842-43, 91 L.Ed. at 1062. Our cases subsequently have recast these

Fictional by design: False; 

### First check: VERIFIED

Gulf Oil passage read on CourtListener.

Excerpt read: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/104393/gulf-oil-corp-v-gilbert/

### Second check: not required


## FNC-0163: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 3.

Authority type: case; as written: 136 Ill.2d 101, 105-06; pincite: 105-06.

Cited for: or example, the availability of compulsory process to secure attendance of unwilling witnesses, the cost to obtain attendance of willing witnesses, and the ability to view the premises (if appropriate). See Griffith v. Mitsubishi Aircraft International, Inc.,

Quotes: []

Context: cost to obtain attendance of willing witnesses, and the ability to view the premises (if appropriate). See Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill.2d 101, 105-06, 143 Ill.Dec. 274, 554 N.E.2d 209 (1990); Bland v. Norfolk & Western Ry. Co., 1

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Griffith, 136 Ill. 2d at 105-06: forum non conveniens factors discussion ending '... decided locally. McClain, 121 Ill. 2d at 289.'

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0164: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217, 506 N.E.2d 1291 (1987)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 3.

Authority type: case; as written: 116 Ill.2d 217, 224; pincite: 224.

Cited for: 274, 554 N.E.2d 209 (1990); Bland v. Norfolk & Western Ry. Co.,

Quotes: []

Context: . See Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill.2d 101, 105-06, 143 Ill.Dec. 274, 554 N.E.2d 209 (1990); Bland v. Norfolk & Western Ry. Co., 116 Ill.2d 217, 224, 107 Ill.Dec. 236, 506 N.E.2d 1291 (1987); see also Adkins, 54 Ill.2d at 514, 3

Fictional by design: False; 

### First check: VERIFIED

Bland text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Bland, 116 Ill. 2d at 224: 'a court must balance private interest factors affecting the convenience of the litigants and public interest factors affecting the administration of the courts.'

- https://www.courtlistener.com/opinion/2210166/bland-v-norfolk-western-railway-co/

### Second check: not required


## FNC-0165: Adkins v. Chicago, Rock Island & Pacific R.R. Co., 54 Ill. 2d 511, 301 N.E.2d 729 (1973)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 3.

Authority type: case; as written: 54 Ill.2d at 514; pincite: 514.

Cited for: Co., 116 Ill.2d 217, 224, 107 Ill.Dec. 236, 506 N.E.2d 1291 (1987); see also Adkins,

Quotes: []

Context: 6, 143 Ill.Dec. 274, 554 N.E.2d 209 (1990); Bland v. Norfolk & Western Ry. Co., 116 Ill.2d 217, 224, 107 Ill.Dec. 236, 506 N.E.2d 1291 (1987); see also Adkins, 54 Ill.2d at 514, 301 N.E.2d 729 (these factors also may include the relative capacities of the

Fictional by design: False; 

### First check: VERIFIED

Adkins passage read on CourtListener.

Excerpt read: 'Forum non conveniens is a doctrine that is founded in considerations of fundamental fairness and sensible and effective judicial administration.'

- https://www.courtlistener.com/opinion/2210722/adkins-v-chi-r-is-pac-rr-co/

### Second check: not required


## FNC-0166: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 3.

Authority type: case; as written: 136 Ill.2d at 106; pincite: 106.

Cited for: and (3) the administrative difficulties presented by adding further litigation to court dockets in already congested fora. See Griffith,

Quotes: []

Context: ion to the litigation; and (3) the administrative difficulties presented by adding further litigation to court dockets in already congested fora. See Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209. Court congestion is a relatively insignifica

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Griffith, 136 Ill. 2d at 106: 'A plaintiffs right to select the forum is a substantial one, and unless the factors weigh strongly in favor of transfer, "the plaintiffs choice of forum should rarely be disturbed."'

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0167: Brummett v. Wepfer Marine, Inc., 111 Ill. 2d 495, 490 N.E.2d 694 (1986)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 3.

Authority type: case; as written: 111 Ill.2d 495, 503; pincite: 503.

Cited for: Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly. See Brummett v. Wepfer Marine, Inc.,

Quotes: []

Context: ively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly. See Brummett v. Wepfer Marine, Inc., 111 Ill.2d 495, 503, 95 Ill.Dec. 841, 490 N.E.2d 694 (1986) (“Courts should be extremely reluctant

Fictional by design: False; 

### First check: VERIFIED

Brummett passages read on CourtListener.

Excerpt read: 'Courts should be extremely reluctant to dismiss a case from the forum rei gestae merely because that forum's docket has a backlog; and this factor is entitled to almost no weight without evidence ...'

- https://www.courtlistener.com/opinion/2251509/brummett-v-wepfer-marine-inc/

### Second check: not required


## FNC-0168: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 3.

Authority type: case; as written: 136 Ill.2d at 106; pincite: 106.

Cited for: The plaintiff has a substantial interest in choosing the forum where his rights will be vindicated, and the plaintiff's forum choice should rarely be disturbed unless the other factors strongly favor transfer. Griffith,

Quotes: []

Context: um where his rights will be vindicated, and the plaintiff's forum choice should rarely be disturbed unless the other factors strongly favor transfer. Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones v. Searle Laboratories, 93 Ill.2d 366,

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Griffith, 136 Ill. 2d at 106: 'A plaintiffs right to select the forum is a substantial one, and unless the factors weigh strongly in favor of transfer, "the plaintiffs choice of forum should rarely be disturbed."'

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0169: Jones v. Searle Laboratories, 93 Ill. 2d 366, 444 N.E.2d 157 (1982)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 3.

Authority type: case; as written: 93 Ill.2d 366, 372-73; pincite: 372-73.

Cited for: Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones v. Searle Laboratories,

Quotes: []

Context: ely be disturbed unless the other factors strongly favor transfer. Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones v. Searle Laboratories, 93 Ill.2d 366, 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157 (1982), quoting Gulf Oil, 330 U.S. at 508-09,

Fictional by design: False; 

### First check: VERIFIED

Jones passage read on CourtListener.

Excerpt read: Jones quotes Gulf Oil: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/2032797/jones-v-searle-laboratories/

### Second check: not required


## FNC-0170: Gulf Oil Corp. v. Gilbert, 330 U.S. 501 (1947)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 3.

Authority type: case; as written: 330 U.S. at 508-09; pincite: 508-09.

Cited for: Searle Laboratories, 93 Ill.2d 366, 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157 (1982), quoting Gulf Oil,

Quotes: []

Context: Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones v. Searle Laboratories, 93 Ill.2d 366, 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157 (1982), quoting Gulf Oil, 330 U.S. at 508-09, 67 S.Ct. at 843, 91 L.Ed. at 1062- 63; see Restatement (Second) of Conflict of

Fictional by design: False; 

### First check: VERIFIED

Gulf Oil passage read on CourtListener.

Excerpt read: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/104393/gulf-oil-corp-v-gilbert/

### Second check: not required


## FNC-0171: Restatement (Second) of Conflict of Laws § 84 cmt. c (1971)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 3.

Authority type: restatement_or_treatise; as written: Restatement (Second) of Conflict of Laws § 84, Comment c; pincite: .

Cited for: 118, 444 N.E.2d 157 (1982), quoting Gulf Oil, 330 U.S. at 508-09, 67 S.Ct. at 843, 91 L.Ed. at 1062- 63; see

Quotes: []

Context: e Laboratories, 93 Ill.2d 366, 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157 (1982), quoting Gulf Oil, 330 U.S. at 508-09, 67 S.Ct. at 843, 91 L.Ed. at 1062- 63; see Restatement (Second) of Conflict of Laws § 84, Comment c (1971) (“since it is for the plaintiff to choose the place of suit, his choice

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The attached opinion reproduces the asserted Restatement language, and another court opinion independently quotes part of comment c, but I did not obtain the ALI Restatement (Second) of Conflict of Laws §84 comment c itself. A quotation in a judicial opinion corroborates the wording but does not satisfy this audit’s direct-source reading requirement.

Excerpt read: The judicial reproductions say plaintiff choice should not be disturbed except for weighty reasons and dismissal requires a suitable alternative forum; ALI source text not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf
- https://www.ali.org/publications/restatement-law-second/conflict-laws
- https://cases.justia.com/montana/supreme-court/2015-da-14-0465.pdf

### Second check: not required


## FNC-0172: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 136 Ill.2d at 106; pincite: 106.

Cited for:  We acknowledge, however, that the plaintiff's interest in choosing the forum receives somewhat less deference when neither the plaintiff's residence nor the site of the accident or injury is located in the chosen forum. Griffith,

Quotes: []

Context: forum receives somewhat less deference when neither the plaintiff's residence nor the site of the accident or injury is located in the chosen forum. Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209. “ When the home forum is chosen, it is reaso

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Griffith, 136 Ill. 2d at 106: 'A plaintiffs right to select the forum is a substantial one, and unless the factors weigh strongly in favor of transfer, "the plaintiffs choice of forum should rarely be disturbed."'

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0173: Wieser v. Missouri Pacific R.R. Co., 98 Ill. 2d 359, 456 N.E.2d 98 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 98 Ill.2d 359, 367; pincite: 367.

Cited for: When the plaintiff is foreign to the forum chosen, however, this assumption is much less reasonable and the plaintiff's choice deserves less deference.” Wieser v. Missouri Pacific R.R. Co.,

Quotes: []

Context: to the forum chosen, however, this assumption is much less reasonable and the plaintiff's choice deserves less deference.” Wieser v. Missouri Pacific R.R. Co., 98 Ill.2d 359, 367, 74 Ill.Dec. 596, 456 N.E.2d 98 (1983); accord Bland v. Norfolk & Western Ry. C

Fictional by design: False; 

### First check: VERIFIED

Quoted language located verbatim in Wieser on CourtListener.

Excerpt read: 'When the home forum is chosen, it is reasonable to assume that the choice is convenient. When the plaintiff is foreign to the forum chosen, however, this assumption is much less reasonable and the plaintiff's choice deserves less deference.'

- https://www.courtlistener.com/opinion/2103250/wieser-v-missouri-pacific-railroad/

### Second check: not required


## FNC-0174: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217, 506 N.E.2d 1291 (1987)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 116 Ill.2d 217, 228; pincite: 228.

Cited for: 596, 456 N.E.2d 98 (1983); accord Bland v. Norfolk & Western Ry. Co.,

Quotes: []

Context: ves less deference.” Wieser v. Missouri Pacific R.R. Co., 98 Ill.2d 359, 367, 74 Ill.Dec. 596, 456 N.E.2d 98 (1983); accord Bland v. Norfolk & Western Ry. Co., 116 Ill.2d 217, 228, 107 Ill.Dec. 236, 506 N.E.2d 1291 (1987), quoting Piper Aircraft Co. v. Reyno,

Fictional by design: False; 

### First check: VERIFIED

Bland text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Bland, 116 Ill. 2d at 228 (quoting Piper): 'When the home forum has been chosen, it is reasonable to assume that this choice is convenient. When the plaintiff is foreign ..., however, this assumption is much less reasonable.'

- https://www.courtlistener.com/opinion/2210166/bland-v-norfolk-western-railway-co/

### Second check: not required


## FNC-0175: Piper Aircraft Co. v. Reyno, 454 U.S. 235 (1981)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 454 U.S. 235, 255-56; pincite: 255-56.

Cited for: 236, 506 N.E.2d 1291 (1987), quoting Piper Aircraft Co. v. Reyno,

Quotes: []

Context: .E.2d 98 (1983); accord Bland v. Norfolk & Western Ry. Co., 116 Ill.2d 217, 228, 107 Ill.Dec. 236, 506 N.E.2d 1291 (1987), quoting Piper Aircraft Co. v. Reyno, 454 U.S. 235, 255-56, 102 S.Ct. 252, 266, 70 L.Ed.2d 419, 436 (1981); but see Elling v. State Farm M

Fictional by design: False; 

### First check: VERIFIED

Piper passage read on CourtListener (star pages).

Excerpt read: 'If central emphasis were placed on any one factor, the forum non conveniens doctrine would lose much of the very flexibility that makes it so valuable.' (*249-50)

- https://www.courtlistener.com/opinion/110586/piper-aircraft-co-v-reyno/

### Second check: not required


## FNC-0176: Elling v. State Farm Mutual Automobile Insurance Co., 291 Ill. App. 3d 311, 683 N.E.2d 929 (1997)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 291 Ill.App.3d 311, 318; pincite: 318.

Cited for: but see Elling v. State Farm Mutual Automobile Insurance Co.,

Quotes: []

Context: iper Aircraft Co. v. Reyno, 454 U.S. 235, 255-56, 102 S.Ct. 252, 266, 70 L.Ed.2d 419, 436 (1981); but see Elling v. State Farm Mutual Automobile Insurance Co., 291 Ill.App.3d 311, 318, 225 Ill.Dec. 426, 683 N.E.2d 929 (1997) (“[W]hile the deference to be accorded

Fictional by design: False; 

### First check: VERIFIED

Quoted language located in Elling (the ellipsis omits 'or where the injury occurred').

Excerpt read: 'while the deference to be accorded to a plaintiff regarding his choice of forum is less when the plaintiff chooses a forum other than where he resides or where the injury occurred, nonetheless the deference to be accorded is only less, as opposed to none'

- https://www.courtlistener.com/opinion/2052172/elling-v-state-farm-mutual-automobile-insurance/

### Second check: not required


## FNC-0177: Brummett v. Wepfer Marine, Inc., 111 Ill. 2d 495, 490 N.E.2d 694 (1986)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 111 Ill.2d at 500; pincite: 500.

Cited for: Similarly, when the site of the accident or injury is chosen, the choice is convenient because the litigation has the aspect of being “decided at home.” See Brummett,

Quotes: []

Context: ly, when the site of the accident or injury is chosen, the choice is convenient because the litigation has the aspect of being “decided at home.” See Brummett, 111 Ill.2d at 500, 95 Ill.Dec. 841, 490 N.E.2d 694. Contrary to our suggestion in Washington v. I

Fictional by design: False; 

### First check: VERIFIED

Brummett passages read on CourtListener.

Excerpt read: 'Courts should be extremely reluctant to dismiss a case from the forum rei gestae merely because that forum's docket has a backlog; and this factor is entitled to almost no weight without evidence ...'

- https://www.courtlistener.com/opinion/2251509/brummett-v-wepfer-marine-inc/

### Second check: not required


## FNC-0178: Washington v. Illinois Power Co., 144 Ill. 2d 395, 581 N.E.2d 644 (1991)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 144 Ill.2d 395, 399; pincite: 399.

Cited for: Contrary to our suggestion in Washington v. Illinois Power Co.,

Quotes: []

Context: t of being “decided at home.” See Brummett, 111 Ill.2d at 500, 95 Ill.Dec. 841, 490 N.E.2d 694. Contrary to our suggestion in Washington v. Illinois Power Co., 144 Ill.2d 395, 399, 163 Ill.Dec. 490, 581 N.E.2d 644 (1991), the trial court, however, does not we

Fictional by design: False; 

### First check: VERIFIED

Washington passages read on CourtListener.

Excerpt read: 'The trial court's decision will be reversed on review only upon showing that, in deciding as it did, the court clearly abused that discretion.'; 'This court has found the annual report of the Administrative Office of the Illinois Courts to be a proper source of reference in assessing court congestion.'

- https://www.courtlistener.com/opinion/2171002/washington-v-illinois-power-co/

### Second check: not required


## FNC-0179: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 163 Ill.2d at 336-37; pincite: 336-37.

Cited for: Instead, the trial court must evaluate the total circumstances of the case in deciding whether the defendant has proven that the balance of factors strongly favors transfer. Peile,

Quotes: []

Context: urt must evaluate the total circumstances of the case in deciding whether the defendant has proven that the balance of factors strongly favors transfer. Peile, 163 Ill.2d at 336-37, 206 Ill.Dec. 179, 645 N.E.2d 184; see Bland, 116 Ill.2d at 227, 107 Ill.Dec. 2

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Peile, 163 Ill. 2d at 336-37: 'The doctrine of forum non conveniens is a flexible one which requires evaluation of the total circumstances rather than concentration on any single factor.'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0180: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217, 506 N.E.2d 1291 (1987)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 116 Ill.2d at 227; pincite: 227.

Cited for: Peile, 163 Ill.2d at 336-37, 206 Ill.Dec. 179, 645 N.E.2d 184; see Bland,

Quotes: []

Context: hether the defendant has proven that the balance of factors strongly favors transfer. Peile, 163 Ill.2d at 336-37, 206 Ill.Dec. 179, 645 N.E.2d 184; see Bland, 116 Ill.2d at 227, 107 Ill.Dec. 236, 506 N.E.2d 1291 (“ ‘If central emphasis were placed on any o

Fictional by design: False; 

### First check: VERIFIED

Bland text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Bland, 116 Ill. 2d at 227: 'To do so would allow a plaintiff to easily frustrate the forum non conveniens principle by selecting as a witness a treating physician or expert in what would, in reality, be an inconvenient forum.'

- https://www.courtlistener.com/opinion/2210166/bland-v-norfolk-western-railway-co/

### Second check: not required


## FNC-0181: Piper Aircraft Co. v. Reyno, 454 U.S. 235 (1981)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 454 U.S. at 249-50; pincite: 249-50.

Cited for: 236, 506 N.E.2d 1291 (“ ‘If central emphasis were placed on any one factor, the forum non conveniens doctrine would lose much of the very flexibility that makes it so valuable’ ”), quoting Piper Aircraft,

Quotes: []

Context: were placed on any one factor, the forum non conveniens doctrine would lose much of the very flexibility that makes it so valuable’ ”), quoting Piper Aircraft, 454 U.S. at 249-50, 102 S.Ct. at 263, 70 L.Ed.2d at 432. The defendant must show that the plaintif

Fictional by design: False; 

### First check: VERIFIED

Piper passage read on CourtListener (star pages).

Excerpt read: 'If central emphasis were placed on any one factor, the forum non conveniens doctrine would lose much of the very flexibility that makes it so valuable.' (*249-50)

- https://www.courtlistener.com/opinion/110586/piper-aircraft-co-v-reyno/

### Second check: not required


## FNC-0182: Hall v. CBI Industries, Inc., 264 Ill. App. 3d 299, 636 N.E.2d 1037 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 264 Ill.App.3d 299, 303; pincite: 303.

Cited for: The defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and another forum is more convenient to all parties. See Hall v. CBI Industries, Inc.,

Quotes: []

Context: show that the plaintiff's chosen forum is inconvenient to the defendant and another forum is more convenient to all parties. See Hall v. CBI Industries, Inc., 264 Ill.App.3d 299, 303, 201 Ill.Dec. 605, 636 N.E.2d 1037 (1994), citing Kwasniewski v. Schaid, 153 Il

Fictional by design: False; 

### First check: VERIFIED

Hall passage read on CourtListener.

Excerpt read: 'it is almost illogical for defendants to claim forum non conveniens when such a claim is based not on their own inconvenience but on the inconvenience to plaintiffs.'

- https://www.courtlistener.com/opinion/2226835/hall-ex-rel-hall-v-cbi-industries-inc/

### Second check: not required


## FNC-0183: Kwasniewski v. Schaid, 153 Ill. 2d 550, 607 N.E.2d 214 (1992)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 153 Ill.2d 550, 555; pincite: 555.

Cited for: CBI Industries, Inc., 264 Ill.App.3d 299, 303, 201 Ill.Dec. 605, 636 N.E.2d 1037 (1994), citing Kwasniewski v. Schaid,

Quotes: []

Context: e convenient to all parties. See Hall v. CBI Industries, Inc., 264 Ill.App.3d 299, 303, 201 Ill.Dec. 605, 636 N.E.2d 1037 (1994), citing Kwasniewski v. Schaid, 153 Ill.2d 550, 555, 180 Ill.Dec. 320, 607 N.E.2d 214 (1992). The defendant cannot assert that the

Fictional by design: False; 

### First check: VERIFIED

Kwasniewski passage read on CourtListener.

Excerpt read: 'It is all but incongruous for defendants to argue that their own home county is inconvenient.'

- https://www.courtlistener.com/opinion/2092326/kwasniewski-v-schaid/

### Second check: not required


## FNC-0184: Whirlpool Corp. v. Certain Underwriters at Lloyd's London, 295 Ill. App. 3d 828, 692 N.E.2d 1229 (1998)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 4.

Authority type: case; as written: 295 Ill.App.3d 828, 837; pincite: 837.

Cited for: See Whirlpool Corp. v. Certain Underwriters at Lloyd's London,

Quotes: []

Context: The defendant cannot assert that the plaintiff's chosen forum is inconvenient to the plaintiff. See Whirlpool Corp. v. Certain Underwriters at Lloyd's London, 295 Ill.App.3d 828, 837, 230 Ill.Dec. 63, 692 N.E.2d 1229 (1998). Our last full discussion of the forum

Fictional by design: False; 

### First check: VERIFIED

Whirlpool passage read on CourtListener.

Excerpt read: 'In other words, the defendant cannot assert the plaintiffs chosen forum is inconvenient to the plaintiff.'

- https://www.courtlistener.com/opinion/2085508/whirlpool-corp-v-certain-underwriters-at-lloyds-london/

### Second check: not required


## FNC-0185: Torres v. Walsh, 98 Ill. 2d 338, 456 N.E.2d 601 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 5.

Authority type: case; as written: 98 Ill.2d 338; pincite: .

Cited for: We acknowledged the frustrating litigation quagmire created in the wake of Torres v. Walsh,

Quotes: []

Context: st adherence to the intrastate application of forum non conveniens. We acknowledged the frustrating litigation quagmire created in the wake of Torres v. Walsh, 98 Ill.2d 338, 74 Ill.Dec. 880, 456 N.E.2d 601 (1983), where we first applied the forum non c

Fictional by design: False; 

### First check: VERIFIED

Torres passages read on CourtListener (CourtListener lacks the 74 Ill. Dec. parallel, which is not a defect). Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: 'the doctrine of forum non conveniens is a discretionary power which should be exercised only in exceptional circumstances when it has been shown that the interests of justice require a trial in a more convenient forum.'

- https://www.courtlistener.com/opinion/2103179/torres-v-walsh/

### Second check: not required


## FNC-0186: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 5.

Authority type: case; as written: 163 Ill.2d at 335; pincite: 335.

Cited for: 880, 456 N.E.2d 601 (1983), where we first applied the forum non conveniens doctrine to intrastate transfers, even agreeing with a concurring justice in the appellate court that “ ‘[t]he battle over the forum results in a battle over minutiae.’ ” Peile,

Quotes: []

Context: tate transfers, even agreeing with a concurring justice in the appellate court that “ ‘[t]he battle over the forum results in a battle over minutiae.’ ” Peile, 163 Ill.2d at 335, 206 Ill.Dec. 179, 645 N.E.2d 184, quoting Peile v. Skelgas, Inc., 242 Ill.App.

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Peile, 163 Ill. 2d at 335: 'Justice Lewis aptly notes that "[t]he battle over the forum results in a battle over minutiae."'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0187: Peile v. Skelgas, Inc., 242 Ill. App. 3d 500, 610 N.E.2d 813 (5th Dist. 1993) (Lewis, J., specially concurring)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 5.

Authority type: case; as written: 242 Ill.App.3d 500, 522; pincite: 522.

Cited for: trine to intrastate transfers, even agreeing with a concurring justice in the appellate court that “ ‘[t]he battle over the forum results in a battle over minutiae.’ ” Peile, 163 Ill.2d at 335, 206 Ill.Dec. 179, 645 N.E.2d 184, quoting Peile v. Skelgas, Inc.,

Quotes: []

Context: ‘[t]he battle over the forum results in a battle over minutiae.’ ” Peile, 163 Ill.2d at 335, 206 Ill.Dec. 179, 645 N.E.2d 184, quoting Peile v. Skelgas, Inc., 242 Ill.App.3d 500, 522, 182 Ill.Dec. 944, 610 N.E.2d 813 (1993) (Lewis, J., specially concurring). How

Fictional by design: False; 

### First check: VERIFIED

Quoted sentence located in the appellate special concurrence on CourtListener.

Excerpt read: Lewis special concurrence: 'The battle over the forum results in a battle over minutiae.'

- https://www.courtlistener.com/opinion/2110774/peile-v-skelgas-inc/

### Second check: not required


## FNC-0188: Torres v. Walsh, 98 Ill. 2d 338, 456 N.E.2d 601 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 5.

Authority type: case; as written: 98 Ill.2d at 346; pincite: 346.

Cited for: s activated in Torres was designed to give the courts ‘discretionary power which should be exercised only in exceptional circumstances when it has been shown that the interests of justice require a trial in a more convenient forum.’ (Emphasis added.) (Torres,

Quotes: []

Context: only in exceptional circumstances when it has been shown that the interests of justice require a trial in a more convenient forum.’ (Emphasis added.) (Torres, 98 Ill.2d at 346, 74 Ill.Dec. 880, 456 N.E.2d 601, citing Gulf Oil, 330 U.S. 501, 67 S.Ct. 839,

Fictional by design: False; 

### First check: VERIFIED

Torres passages read on CourtListener (CourtListener lacks the 74 Ill. Dec. parallel, which is not a defect). Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Torres, 98 Ill. 2d at 346: 'the doctrine of forum non conveniens is a discretionary power which should be exercised only in exceptional circumstances when it has been shown that the interests of justice require a trial in a more convenient forum.'

- https://www.courtlistener.com/opinion/2103179/torres-v-walsh/

### Second check: not required


## FNC-0189: Gulf Oil Corp. v. Gilbert, 330 U.S. 501 (1947)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 5.

Authority type: case; as written: 330 U.S. 501; pincite: .

Cited for:  power which should be exercised only in exceptional circumstances when it has been shown that the interests of justice require a trial in a more convenient forum.’ (Emphasis added.) (Torres, 98 Ill.2d at 346, 74 Ill.Dec. 880, 456 N.E.2d 601, citing Gulf Oil,

Quotes: []

Context: nterests of justice require a trial in a more convenient forum.’ (Emphasis added.) (Torres, 98 Ill.2d at 346, 74 Ill.Dec. 880, 456 N.E.2d 601, citing Gulf Oil, 330 U.S. 501, 67 S.Ct. 839, 91 L.Ed. 1055.) In most instances, the plaintiff's initial choic

Fictional by design: False; 

### First check: VERIFIED

Gulf Oil passage read on CourtListener.

Excerpt read: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/104393/gulf-oil-corp-v-gilbert/

### Second check: not required


## FNC-0190: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 5.

Authority type: case; as written: 163 Ill.2d at 335-36; pincite: 335-36.

Cited for: Accordingly, we decline the invitation to abandon intrastate transfer of cases when appropriate, under the principles enunciated in Torres v. Walsh.” Peile,

Quotes: []

Context: e. Accordingly, we decline the invitation to abandon intrastate transfer of cases when appropriate, under the principles enunciated in Torres v. Walsh.” Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179, 645 N.E.2d 184. Since Peile, we have exercised our superviso

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Peile, 163 Ill. 2d at 335-36: 'The doctrine that was activated in Torres was designed to give the courts "discretionary power which should be exercised only in exceptional circumstances ..." In most instances, the plaintiffs initial choice of forum will prevail'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0191: Torres v. Walsh, 98 Ill. 2d 338, 456 N.E.2d 601 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 5.

Authority type: case; as written: 98 Ill.2d at 351; pincite: 351.

Cited for: A concern animating our forum non conveniens jurisprudence is curtailing forum shopping by plaintiffs. See Torres,

Quotes: []

Context: her a body of law to guide the trial courts. A concern animating our forum non conveniens jurisprudence is curtailing forum shopping by plaintiffs. See Torres, 98 Ill.2d at 351, 74 Ill.Dec. 880, 456 N.E.2d 601 (discouraging “the incessant jockeying for a m

Fictional by design: False; 

### First check: VERIFIED

Torres passages read on CourtListener (CourtListener lacks the 74 Ill. Dec. parallel, which is not a defect). Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Torres, 98 Ill. 2d at 351: 'discourage the incessant jockeying for a more sympathetic jury likely to come forward with a more substantial award'; (as quoted in Boner) 'the defendant's inconvenience should not be considered, provided venue is proper.'

- https://www.courtlistener.com/opinion/2103179/torres-v-walsh/

### Second check: not required


## FNC-0192: G. Maag, Forum Non Conveniens in Illinois: A Historical Review, Critical Analysis, and Proposal for Change, 25 S. Ill. U. L.J. 461 (2001)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 6.

Authority type: other; as written: 25 So. Ill. L.J. 461, 510; pincite: .

Cited for: Maag, Forum Non Conveniens in Illinois: A Historical Review, Critical Analysis, and Proposal for Change,

Quotes: []

Context: other considerations are secondary to both sides.” G. Maag, Forum Non Conveniens in Illinois: A Historical Review, Critical Analysis, and Proposal for Change, 25 So. Ill. L.J. 461, 510 (2001). See also E. Kitch, Section 1404(a) of the Judicial Code: In the Interes

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Guerine quotes Gordon E. Maag at page 510, but the actual 2001 Southern Illinois University Law Journal article was not accessible for direct reading. Repository searches located later volumes or secondary citations, not the cited page.

Excerpt read: Guerine quotes: both sides seek a favorable judge, jury, and forum; Maag article page 510 not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf
- https://opensiuc.lib.siu.edu/siulj/vol25/iss1/

### Second check: not required


## FNC-0193: E. Kitch, Section 1404(a) of the Judicial Code: In the Interest of Justice or Injustice?, 40 Ind. L.J. 99 (1965)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 6.

Authority type: other; as written: 40 Ind. L.J. 99, 139; pincite: .

Cited for: Kitch, Section 1404(a) of the Judicial Code: In the Interest of Justice or Injustice?,

Quotes: []

Context: , and Proposal for Change, 25 So. Ill. L.J. 461, 510 (2001). See also E. Kitch, Section 1404(a) of the Judicial Code: In the Interest of Justice or Injustice?, 40 Ind. L.J. 99, 139 (1965) (“[B]ehind the talk of inconvenience and the interests of justice lies a

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Indiana Law Journal repository identifies Edmund Kitch’s article and offers a PDF link, but its full-text endpoint returned HTTP 403; the article at page 139 was not read. Guerine’s quotation cannot substitute for direct article text.

Excerpt read: Guerine quotes Kitch: behind talk of inconvenience and justice lies concern about juries; article page 139 not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf
- https://www.repository.law.indiana.edu/ilj/vol40/iss2/
- https://www.repository.law.indiana.edu/cgi/viewcontent.cgi?article=3563&context=ilj

### Second check: not required


## FNC-0194: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 6.

Authority type: case; as written: 136 Ill.2d at 107; pincite: 107.

Cited for: 99, 139 (1965) (“[B]ehind the talk of inconvenience and the interests of justice lies a concern not about plane fares but about juries”). Under the “unequal balancing test” (Griffith,

Quotes: []

Context: d the talk of inconvenience and the interests of justice lies a concern not about plane fares but about juries”). Under the “unequal balancing test” (Griffith, 136 Ill.2d at 107, 143 Ill.Dec. 274, 554 N.E.2d 209), the plaintiff is entitled to some deference

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Griffith, 136 Ill. 2d at 107: defendants' proposed 'equal balancing test' rejected; the unequal test requires that the factors 'strongly favor' transfer.

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0195: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 6.

Authority type: case; as written: 163 Ill.2d at 336; pincite: 336.

Cited for: Though the plaintiff's choice is not absolute, intrastate transfer is appropriate only when the litigation has “no practical connection” (Peile,

Quotes: []

Context: y in the lead. Though the plaintiff's choice is not absolute, intrastate transfer is appropriate only when the litigation has “no practical connection” (Peile, 163 Ill.2d at 336, 206 Ill.Dec. 179, 645 N.E.2d 184), no nexus, with the plaintiff's chosen forum

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Peile, 163 Ill. 2d at 336: 'The trial court is vested with considerable discretion in its determination of whether transfer is warranted'; 'If, however, the litigation has no practical connection to the forum ... the court should grant the motion for transfer.'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0196: Torres v. Walsh, 98 Ill. 2d 338, 456 N.E.2d 601 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 6.

Authority type: case; as written: 98 Ill.2d at 345-47; pincite: 345-47.

Cited for: We reviewed Gulf Oil and noted that courts in 18 other states have statutory authority to order intrastate venue transfers. Torres,

Quotes: []

Context: court for mandamus relief. We reviewed Gulf Oil and noted that courts in 18 other states have statutory authority to order intrastate venue transfers. Torres, 98 Ill.2d at 345-47, 74 Ill.Dec. 880, 456 N.E.2d 601. We further noted that at common law, English

Fictional by design: False; 

### First check: VERIFIED

Torres passages read on CourtListener (CourtListener lacks the 74 Ill. Dec. parallel, which is not a defect). Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Torres, 98 Ill. 2d at 346: 'Courts in many of our sister States throughout the country have the statutory authority to transfer cases to other counties within the same State on the grounds of forum non conveniens'

- https://www.courtlistener.com/opinion/2103179/torres-v-walsh/

### Second check: not required


## FNC-0197: Torres v. Walsh, 98 Ill. 2d 338, 456 N.E.2d 601 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 6.

Authority type: case; as written: 98 Ill.2d at 347-48; pincite: 347-48.

Cited for: We further noted that at common law, English courts had the authority to remove a case to another county in order to obtain an impartial trial or to minimize the inconvenience of witnesses residing a great distance away from the chosen forum. Torres,

Quotes: []

Context: nother county in order to obtain an impartial trial or to minimize the inconvenience of witnesses residing a great distance away from the chosen forum. Torres, 98 Ill.2d at 347-48, 74 Ill.Dec. 880, 456 N.E.2d 601. After discussing our interstate forum non con

Fictional by design: False; 

### First check: VERIFIED

Torres passages read on CourtListener (CourtListener lacks the 74 Ill. Dec. parallel, which is not a defect). Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Torres, 98 Ill. 2d at 348: 'when an impartial trial could not be obtained the court of the King's Bench had the authority to transfer the trial to the next adjoining county ... where the witnesses resided at a great distance'

- https://www.courtlistener.com/opinion/2103179/torres-v-walsh/

### Second check: not required


## FNC-0198: Torres v. Walsh, 98 Ill. 2d 338, 456 N.E.2d 601 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 6.

Authority type: case; as written: 98 Ill.2d at 350; pincite: 350.

Cited for: Louis, Missouri, we feel that a case should be able to be transferred from Chicago to Springfield-two cities in the same State-under the same theory.” Torres,

Quotes: []

Context: Louis, Missouri, we feel that a case should be able to be transferred from Chicago to Springfield-two cities in the same State-under the same theory.” Torres, 98 Ill.2d at 350, 74 Ill.Dec. 880, 456 N.E.2d 601. We reiterated the relevant factors for trial

Fictional by design: False; 

### First check: VERIFIED

Torres passages read on CourtListener (CourtListener lacks the 74 Ill. Dec. parallel, which is not a defect). Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Torres, 98 Ill. 2d at 350: 'a case should be able to be transferred from Chicago to Springfield - two cities in the same State - under the same theory.'

- https://www.courtlistener.com/opinion/2103179/torres-v-walsh/

### Second check: not required


## FNC-0199: Torres v. Walsh, 98 Ill. 2d 338, 456 N.E.2d 601 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 6.

Authority type: case; as written: 98 Ill.2d at 351; pincite: 351.

Cited for: We reiterated the relevant factors for trial courts to consider, but we warned that if sufficient factors favor the plaintiff's forum choice, “the defendant's inconvenience should not be considered, provided venue is proper.” Torres,

Quotes: []

Context: rned that if sufficient factors favor the plaintiff's forum choice, “the defendant's inconvenience should not be considered, provided venue is proper.” Torres, 98 Ill.2d at 351, 74 Ill.Dec. 880, 456 N.E.2d 601. Because we determined that the trial court ha

Fictional by design: False; 

### First check: VERIFIED

Torres passages read on CourtListener (CourtListener lacks the 74 Ill. Dec. parallel, which is not a defect). Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Torres, 98 Ill. 2d at 351: 'discourage the incessant jockeying for a more sympathetic jury likely to come forward with a more substantial award'; (as quoted in Boner) 'the defendant's inconvenience should not be considered, provided venue is proper.'

- https://www.courtlistener.com/opinion/2103179/torres-v-walsh/

### Second check: not required


## FNC-0200: Torres v. Walsh, 98 Ill. 2d 338, 456 N.E.2d 601 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 6.

Authority type: case; as written: 98 Ill.2d at 353; pincite: 353.

Cited for: Because we determined that the trial court had discretion to order an intrastate transfer, mandamus relief was inappropriate. Torres,

Quotes: []

Context: Dec. 880, 456 N.E.2d 601. Because we determined that the trial court had discretion to order an intrastate transfer, mandamus relief was inappropriate. Torres, 98 Ill.2d at 353, 74 Ill.Dec. 880, 456 N.E.2d 601. More recently, in a case remarkably similar t

Fictional by design: False; 

### First check: VERIFIED

Torres passages read on CourtListener (CourtListener lacks the 74 Ill. Dec. parallel, which is not a defect). Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Torres, 98 Ill. 2d at 353: 'we must deny the issuance of a writ of mandamus.'

- https://www.courtlistener.com/opinion/2103179/torres-v-walsh/

### Second check: not required


## FNC-0201: Hinshaw v. Coachmen Industries, Inc., 319 Ill. App. 3d 269, 745 N.E.2d 583 (2001)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 6.

Authority type: case; as written: 319 Ill.App.3d 269; pincite: .

Cited for: More recently, in a case remarkably similar to the one before us, the First District upheld the plaintiff's forum choice. In Hinshaw v. Coachmen Industries, Inc.,

Quotes: []

Context: e recently, in a case remarkably similar to the one before us, the First District upheld the plaintiff's forum choice. In Hinshaw v. Coachmen Industries, Inc., 319 Ill.App.3d 269, 253 Ill.Dec. 460, 745 N.E.2d 583 (2001), the plaintiffs filed a complaint in C

Fictional by design: False; 

### First check: VERIFIED

Hinshaw passages read on CourtListener.

Excerpt read: 'it was not unreasonable for the trial court to conclude that there was no predominance among the counties such that Woodford County was strongly favored.'; 'any local interest on the part of, say, Woodford County is largely supplanted by a more general interest in the safety of Dodge vans.'

- https://www.courtlistener.com/opinion/2182385/hinshaw-v-coachmen-industries-inc/

### Second check: not required


## FNC-0202: Hinshaw v. Coachmen Industries, Inc., 319 Ill. App. 3d 269, 745 N.E.2d 583 (2001)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 7.

Authority type: case; as written: 319 Ill.App.3d at 275; pincite: 275.

Cited for: The appellate court discussed the familiar forum non conveniens factors, including the plaintiffs' forum choice, and stated that “the factors, when viewed in their totality, must strongly favor transfer.” (Emphasis in original.) Hinshaw,

Quotes: []

Context: ding the plaintiffs' forum choice, and stated that “the factors, when viewed in their totality, must strongly favor transfer.” (Emphasis in original.) Hinshaw, 319 Ill.App.3d at 275, 253 Ill.Dec. 460, 745 N.E.2d 583. The court reviewed the private interest fact

Fictional by design: False; 

### First check: VERIFIED

Hinshaw passages read on CourtListener.

Excerpt read: 'it was not unreasonable for the trial court to conclude that there was no predominance among the counties such that Woodford County was strongly favored.'; 'any local interest on the part of, say, Woodford County is largely supplanted by a more general interest in the safety of Dodge vans.'

- https://www.courtlistener.com/opinion/2182385/hinshaw-v-coachmen-industries-inc/

### Second check: not required


## FNC-0203: Hinshaw v. Coachmen Industries, Inc., 319 Ill. App. 3d 269, 745 N.E.2d 583 (2001)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 7.

Authority type: case; as written: 319 Ill.App.3d at 277; pincite: 277.

Cited for: ses and other evidence was scattered across eight Illinois counties and two additional states, “it was not unreasonable for the trial court to conclude that there was no predominance among the counties such that Woodford County was strongly favored.” Hinshaw,

Quotes: []

Context: as not unreasonable for the trial court to conclude that there was no predominance among the counties such that Woodford County was strongly favored.” Hinshaw, 319 Ill.App.3d at 277, 253 Ill.Dec. 460, 745 N.E.2d 583. The court then turned to the public interest

Fictional by design: False; 

### First check: VERIFIED

Hinshaw passages read on CourtListener.

Excerpt read: 'it was not unreasonable for the trial court to conclude that there was no predominance among the counties such that Woodford County was strongly favored.'; 'any local interest on the part of, say, Woodford County is largely supplanted by a more general interest in the safety of Dodge vans.'

- https://www.courtlistener.com/opinion/2182385/hinshaw-v-coachmen-industries-inc/

### Second check: not required


## FNC-0204: Hinshaw v. Coachmen Industries, Inc., 319 Ill. App. 3d 269, 745 N.E.2d 583 (2001)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 7.

Authority type: case; as written: 319 Ill.App.3d at 278; pincite: 278.

Cited for: ed pursuant to a settlement agreement, the case centered around the plaintiffs' products liability claim: “As such, any local interest on the part of, say, Woodford County is largely supplanted by a more general interest in the safety of Dodge vans.” Hinshaw,

Quotes: []

Context: laim: “As such, any local interest on the part of, say, Woodford County is largely supplanted by a more general interest in the safety of Dodge vans.” Hinshaw, 319 Ill.App.3d at 278, 253 Ill.Dec. 460, 745 N.E.2d 583. Unlike Torres, but like Hinshaw, the case be

Fictional by design: False; 

### First check: VERIFIED

Hinshaw passages read on CourtListener.

Excerpt read: 'it was not unreasonable for the trial court to conclude that there was no predominance among the counties such that Woodford County was strongly favored.'; 'any local interest on the part of, say, Woodford County is largely supplanted by a more general interest in the safety of Dodge vans.'

- https://www.courtlistener.com/opinion/2182385/hinshaw-v-coachmen-industries-inc/

### Second check: not required


## FNC-0205: Broeker v. Turville, 257 Ill. App. 3d 389, 628 N.E.2d 996 (1993)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 7.

Authority type: case; as written: 257 Ill.App.3d 389; pincite: .

Cited for: The litigation in this case has a nexus with several fora. See Broeker v. Turville,

Quotes: []

Context: d witnesses dispersed among several counties in the same area of the state. The litigation in this case has a nexus with several fora. See Broeker v. Turville, 257 Ill.App.3d 389, 195 Ill.Dec. 532, 628 N.E.2d 996 (1993); Grachen v. Zarecki, 200 Ill.App.3d 33

Fictional by design: False; 

### First check: VERIFIED

Broeker read on CourtListener; supports a 'see' cite for multi-county nexus.

Excerpt read: 'we conclude that the trial court erred in granting the motion for change of venue based on the doctrine of forum non conveniens as such factors do not strongly weigh in favor of transfer.'

- https://www.courtlistener.com/opinion/2016887/broeker-v-turville/

### Second check: not required


## FNC-0206: Grachen v. Zarecki, 200 Ill. App. 3d 336, 558 N.E.2d 132 (1990)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 7.

Authority type: case; as written: 200 Ill.App.3d 336; pincite: .

Cited for: Turville, 257 Ill.App.3d 389, 195 Ill.Dec. 532, 628 N.E.2d 996 (1993); Grachen v. Zarecki,

Quotes: []

Context: itigation in this case has a nexus with several fora. See Broeker v. Turville, 257 Ill.App.3d 389, 195 Ill.Dec. 532, 628 N.E.2d 996 (1993); Grachen v. Zarecki, 200 Ill.App.3d 336, 146 Ill.Dec. 169, 558 N.E.2d 132 (1990); see also Meyers v. Bridgeport Machine

Fictional by design: False; 

### First check: VERIFIED

Grachen read on CourtListener; supports a 'see' cite for multi-county nexus.

Excerpt read: 'the fact that the collision occurred in Woodford does not have as much impact on the forum non conveniens issue as it might if most of the occurrence witnesses lived in or near Woodford.'

- https://www.courtlistener.com/opinion/2234673/grachen-v-zarecki/

### Second check: not required


## FNC-0207: Meyers v. Bridgeport Machines Division of Textron, Inc., 113 Ill. 2d 112, 497 N.E.2d 745 (1986)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 7.

Authority type: case; as written: 113 Ill.2d 112, 121; pincite: 121.

Cited for: see also Meyers v. Bridgeport Machines Division of Textron, Inc.,

Quotes: []

Context: 996 (1993); Grachen v. Zarecki, 200 Ill.App.3d 336, 146 Ill.Dec. 169, 558 N.E.2d 132 (1990); see also Meyers v. Bridgeport Machines Division of Textron, Inc., 113 Ill.2d 112, 121, 100 Ill.Dec. 567, 497 N.E.2d 745 (1986) (affirming the trial court's denial of

Fictional by design: False; 

### First check: VERIFIED

Meyers passage read on CourtListener.

Excerpt read: 'the factual connections with the forum in this case can be said to be evenly distributed among Cook, McHenry, Lake and Kane counties. That there is not a predominance of connections to any one of the counties supports the trial court's denial ...'

- https://www.courtlistener.com/opinion/2183670/meyers-v-bridgeport-machines-division-of-textron-inc/

### Second check: not required


## FNC-0208: Washington v. Illinois Power Co., 144 Ill. 2d 395, 581 N.E.2d 644 (1991)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 7.

Authority type: case; as written: 144 Ill.2d at 402; pincite: 402.

Cited for: Though these affidavits do not resolve all of the scheduling problems associated with a trial in a forum away from the location of witnesses (see Washington,

Quotes: []

Context: . Though these affidavits do not resolve all of the scheduling problems associated with a trial in a forum away from the location of witnesses (see Washington, 144 Ill.2d at 402, 163 Ill.Dec. 490, 581 N.E.2d 644), they do suggest that the Schumperts are wil

Fictional by design: False; 

### First check: VERIFIED

Washington passages read on CourtListener.

Excerpt read: 'The trial court's decision will be reversed on review only upon showing that, in deciding as it did, the court clearly abused that discretion.'; 'This court has found the annual report of the Administrative Office of the Illinois Courts to be a proper source of reference in assessing court congestion.'

- https://www.courtlistener.com/opinion/2171002/washington-v-illinois-power-co/

### Second check: not required


## FNC-0209: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 8.

Authority type: case; as written: 163 Ill.2d at 345; pincite: 345.

Cited for: Today, convenience-the touchstone of the forum non conveniens doctrine-has a different meaning. See Peile,

Quotes: []

Context: airways, telecommunications, and the world wide web. Today, convenience-the touchstone of the forum non conveniens doctrine-has a different meaning. See Peile, 163 Ill.2d at 345, 206 Ill.Dec. 179, 645 N.E.2d 184 (Harrison, J., dissenting). That is, the conv

Fictional by design: False; 

### First check: VERIFIED

'See' cite to Justice Harrison's dissent in Peile (163 Ill. 2d at 345), which argues that improved highways, air service and communications have eliminated intrastate inconvenience; supports Guerine's 'smaller world' point.

Excerpt read: Peile (Harrison, J., dissenting; CourtListener 9861254): 'The improvement of the highway system, the expansion of scheduled air service, and the spread of new technologies have all but eliminated the obstacles that once hindered the ability of parties to litigate their cases in different parts of the State.'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0210: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 8.

Authority type: case; as written: 163 Ill.2d at 345; pincite: 345.

Cited for: The balance of factors must strongly favor transfer of the case before the plaintiff can be deprived of his chosen forum. See Peile,

Quotes: []

Context: nection to the litigation. The balance of factors must strongly favor transfer of the case before the plaintiff can be deprived of his chosen forum. See Peile, 163 Ill.2d at 345, 206 Ill.Dec. 179, 645 N.E.2d 184. This is not such a case. CONCLUSION For the

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Peile majority (163 Ill. 2d at 345): 'We reiterate and adhere to this court's past statements that the balance of factors must strongly favor the defendants' motion for forum non conveniens before a case should be transferred to a forum other than the one chosen by the plaintiff.'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0211: Wakehouse v. Titan Wheel Corp., 196 Ill. 2d 565 (2001) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 8.

Authority type: case; as written: Wakehouse v. Titan Wheel Corp., 196 Ill.2d 565, 258 Ill.Dec. 174, 755 N.E.2d 993; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: court transferring this cause to Kane County and remand for further proceedings. Reversed and remanded. APPENDIX See Wakehouse v. Titan Wheel Corp., No. 92108, 196 Ill.2d 565, 258 Ill.Dec. 174, 755 N.E.2d 993 (October 3, 2001) (ordering the Fifth Distric

Fictional by design: False; 

### First check: MISCHARACTERIZED

The October 3, 2001 order directs the Fifth District to vacate an affirmance of denial of a motion to dismiss on forum non conveniens grounds and reconsider. Guerine calls it denial of a motion to transfer venue. The procedural remedy is misstated.

Excerpt read: The appellate court is ordered to reconsider the order affirming denial of defendant’s motion to dismiss on forum non conveniens grounds.

- https://www.leagle.com/decision/20011748755ne2d99311712
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: VERIFIED_MINOR_DEFECT

Overturns Sol's MISCHARACTERIZED. I read the October 3, 2001 order on Leagle (755 N.E.2d 993, 258 Ill. Dec. 174, No. 92108). It directs the Fifth District to vacate its July 19, 2001 order affirming the circuit court's denial of the defendant's 'motion to dismiss on forum non conveniens grounds' and to reconsider in light of Vinson v. Allstate; the text is cut off after the Vinson citation. Guerine says 'ordering the Fifth District to reconsider [its] order affirming the trial court's denial of the defendant's forum non conveniens motion to transfer venue.' That is right on the court directed, the act (reconsider), and the appellate affirmance. The only error is the motion type. A primary text confirms that error: the later appellate opinion in the same litigation (Warehouse [sic] v. Goodyear Tire & Rubber Co., 353 Ill. App. 3d 346 (3d Dist. 2004), read on CourtListener) says the motion was 'a motion to dismiss based on improper venue and on the grounds of interstate forum non conveniens', that the Fifth District 'affirmed in a Rule 23 order entered on July 19, 2001', and that 'the supreme court entered a supervisory order vacating the appellate court's order.' So the motion was an interstate dismissal (Nebraska/Iowa), not an intrastate transfer, and the parenthetical's label is wrong. Guerine's appendix reads as a stylized summary, not a precise motion-by-motion description: (1) every one of the roughly 30 entries uses the same phrase, 'forum non conveniens motion to transfer venue', including A.P. Green, whose own order describes a 'motion to dismiss or transfer'; (2) the body sentence that cites the appendix ('Since Peile, we have exercised our supervisory authority more than 30 times to transfer cases away from plaintiffs' chosen fora') counts reconsideration orders (Wakehouse, Popp) and an interlocutory-appeal order (A.P. Green) as instances of 'transfer', so the court is using 'transfer' loosely; (3) the appendix says 'ordering the Fifth District to vacate' even where the supreme court itself vacated the appellate judgment, and those rows were VERIFIED (Kinzler, Beldner). The official reporter text on CourtListener (764 N.E.2d at *64-*66) matches the attachment word for word, including the 'reconsider is order' typo, so these are the court's own words and not artifacts of the copy. House calibration: if the proposition the authority is cited for survives and a parenthetical detail is wrong, the row is VERIFIED_MINOR_DEFECT; MISCHARACTERIZED is reserved for a parenthetical that states a disposition the order does not contain or that is the opposite of it. Wakehouse is still a supervisory order in which the supreme court set aside an FNC ruling that kept the case in the plaintiff's chosen forum. That supports what the appendix cites it for, so the motion label is a minor defect. Under current Rule 187 the dismissal/transfer split is meaningful (187(c)(1) intrastate transfer versus 187(c)(2) dismissal conditions), but it does not change the proposition being supported.

Excerpt read: Order: 'In the exercise of this Court's supervisory authority, the Appellate Court, Fifth District, is directed to vacate its order in Wakehouse v. Goodyear Tire and Rubber Co., case No. 5-99-0749 (July 19, 2001), affirming the circuit court's denial of defendant's motion to dismiss on forum non conveniens grounds. The appellate court is ordered to reconsider in light of Vinson v. Allstate, 144 Ill.2d 306, ...' [truncated]. 353 Ill. App. 3d 346: 'The defendants subsequently filed a motion to dismiss based on improper venue and on the grounds of interstate forum non conveniens. The circuit court denied the motion and, after granting defendants' Rule 306 petition for leave to appeal, the Fifth District Appellate Court affirmed in a Rule 23 order entered on July 19, 2001. ... The supreme court entered a supervisory order vacating the appellate court's order ...'

- https://www.leagle.com/decision/20011748755ne2d99311712
- https://www.courtlistener.com/opinion/3138994/warehouse-v-goodyear-tire-rubber-co/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf
- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/7ae8a196-2a43-4484-9666-43098da60282/S_Ct_Rules_full.pdf

Model: claude-opus-5-5; reasoning effort: high (orchestration-configured).

## FNC-0212: A.P . Green Industries, Inc. v. Houston, 195 Ill. 2d 547 (2001) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 8.

Authority type: case; as written: A.P . Green Industries, Inc. v. Houston, 195 Ill.2d 547, 257 Ill.Dec. 885, 754 N.E.2d 1280; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: onsider is order affirming the trial court's denial of the defendant's forum non conveniens motion to transfer venue); A.P . Green Industries, Inc. v. Houston, 195 Ill.2d 547, 257 Ill.Dec. 885, 754 N.E.2d 1280 (2001) (ordering the Fifth District to allow

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The June 6 order directs the Fifth District to allow an interlocutory appeal from denial of a motion to dismiss or transfer on forum non conveniens grounds. The reporter caption is In re A.P. Green Industries, Inc., with Houston in the parenthetical party description, while the Guerine appendix calls it A.P. Green Industries v. Houston.

Excerpt read: The Appellate Court, Fifth District, is directed to enter an order in Houston v. ACandS allowing an interlocutory appeal of denial of a motion to dismiss or transfer based on forum non conveniens.

- https://www.leagle.com/decision/20012034754ne2d128031999
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: VERIFIED_MINOR_DEFECT

I tried to upgrade this to VERIFIED and could not; Sol's minor-defect rating stands. The June 6, 2001 order (754 N.E.2d 1280, 195 Ill. 2d 547, 257 Ill. Dec. 885, No. 91077) directs the Fifth District to allow an interlocutory appeal, in Houston v. ACandS and Geyer v. ACandS, of 'the order denying the motion to dismiss or transfer based on forum non conveniens.' That supports the appendix's disposition, and the relevant language appears before Leagle's cutoff ('and to enter a decision...'). The appendix's 'motion to transfer venue' is its standard gloss and reasonably describes a 'dismiss or transfer' motion. The defect is the caption. The reporter caption is 'In re A.P. Green Industries, Inc., et al., etc. (ACandS, Inc., petitioner, v. Jerri L. Houston, etc., respondent).' Guerine's 'A.P. Green Industries, Inc. v. Houston' invents an adversarial caption that names A.P. Green rather than ACandS as the party opposing Houston. The citation and parallels are correct.

Excerpt read: 'In re A.P. GREEN INDUSTRIES, INC., et al., etc. (ACandS, Inc., petitioner, v. Jerri L. Houston, etc., respondent).' ... 'the Appellate Court, Fifth District, is directed to enter an order in the cases of Houston v. ACandS, case No. 00 L 850, and Geyer v. ACandS, case No. 00 L 852, allowing an interlocutory appeal of the order denying the motion to dismiss or transfer based on forum non conveniens, and to enter a decision...' [truncated]

- https://www.leagle.com/decision/20012034754ne2d128031999
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

Model: claude-opus-5-5; reasoning effort: high (orchestration-configured).

## FNC-0213: Armstrong World Industries, Inc. v. Geyer, 195 Ill. 2d 547 (2001) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 8.

Authority type: case; as written: Armstrong World Industries, Inc. v. Geyer, 195 Ill.2d 547, 257 Ill.Dec. 886, 754 N.E.2d 1281; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: interlocutory appeal of the trial court's denial of the defendant's forum non conveniens motion to transfer venue); Armstrong World Industries, Inc. v. Geyer, 195 Ill.2d 547, 257 Ill.Dec. 886, 754 N.E.2d 1281 (2001) (same); Olin v. A.P . Green Industrie

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The same June 6 supervisory order covers Geyer and directs an interlocutory appeal. The reporter caption is In re Armstrong World Industries, Inc., with Geyer in the party description, while the appendix uses Armstrong World Industries v. Geyer.

Excerpt read: The Appellate Court, Fifth District, is directed to enter an order in Geyer v. ACandS allowing an interlocutory appeal of denial of a motion to dismiss or transfer based on forum non conveniens.

- https://www.leagle.com/decision/20012035754ne2d128111999
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: VERIFIED_MINOR_DEFECT

Upheld after trying to upgrade it to VERIFIED. The companion June 6, 2001 order (754 N.E.2d 1281, 195 Ill. 2d 547, 257 Ill. Dec. 886, No. 91078) has the same operative text: it directs the Fifth District to allow an interlocutory appeal of the denial of the motion to dismiss or transfer based on forum non conveniens in Geyer v. ACandS. That supports the appendix's '(same)', and the operative language is visible before the cutoff. Caption defect: the reporter caption is 'In re Armstrong World Indutries [sic], Inc., et al., etc. (ACandS, Inc., petitioner, v. Benjamin Geyer, respondent).' Guerine's 'Armstrong World Industries, Inc. v. Geyer' names the wrong moving party in an adversarial form. The citation and parallels are correct.

Excerpt read: 'In re ARMSTRONG WORLD INDUTRIES, INC., et al., etc. (ACandS, Inc., petitioner, v. Benjamin Geyer, respondent).' ... 'directed to enter an order in the cases of Houston v. ACandS, case No. 00 L 850, and Geyer v. ACandS, case No. 00 L 852, allowing an interlocutory appeal of the order denying the motion to dismiss or transfer based on forum non conveniens, and to enter a decision...' [truncated]

- https://www.leagle.com/decision/20012035754ne2d128111999
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

Model: claude-opus-5-5; reasoning effort: high (orchestration-configured).

## FNC-0214: Olin v. A.P . Green Industries, Inc., 192 Ill. 2d 693 (2000) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 8.

Authority type: case; as written: Olin v. A.P . Green Industries, Inc., 192 Ill.2d 693, 250 Ill.Dec. 292, 738 N.E.2d 508; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: nsfer venue); Armstrong World Industries, Inc. v. Geyer, 195 Ill.2d 547, 257 Ill.Dec. 886, 754 N.E.2d 1281 (2001) (same); Olin v. A.P . Green Industries, Inc., 192 Ill.2d 693, 250 Ill.Dec. 292, 738 N.E.2d 508 (2000)

Fictional by design: False; 

### First check: VERIFIED

The order vacates Madison County’s denial of a forum non conveniens transfer motion and directs entry of an order granting it.

Excerpt read: The order of the Circuit Court of Madison County denying defendants’ motion to transfer based on forum non conveniens is vacated; the court is directed to grant defendants’ motion.

- https://www.leagle.com/decision/20001246738ne2d50821231
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0215: Cerniglia v. Armstrong World Industries, Inc., 189 Ill. 2d 656 (2000) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Cerniglia v. Armstrong World Industries, Inc., 189 Ill.2d 656, 246 Ill.Dec. 377, 730 N.E.2d 57; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: dering the Madison County circuit court to grant the defendant's forum non conveniens motion to transfer venue); Cerniglia v. Armstrong World Industries, Inc., 189 Ill.2d 656, 246 Ill.Dec. 377, 730 N.E.2d 57 (2000) (same); Hairrell v. Winterville Marine

Fictional by design: False; 

### First check: VERIFIED

The order vacates Madison County’s denial of venue transfer based on forum non conveniens and directs grant of defendants’ motions.

Excerpt read: Petition for leave to appeal denied; in supervisory authority, the Madison County denial of motions to transfer venue based on forum non conveniens is vacated and the court is directed to grant the motions.

- https://www.leagle.com/decision/2000787730ne2d573760
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0216: Hairrell v. Winterville Marine Service Co., 187 Ill. 2d 567 (2000) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Hairrell v. Winterville Marine Service Co., 187 Ill.2d 567, 243 Ill.Dec. 77, 722 N.E.2d 1146; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: nue); Cerniglia v. Armstrong World Industries, Inc., 189 Ill.2d 656, 246 Ill.Dec. 377, 730 N.E.2d 57 (2000) (same); Hairrell v. Winterville Marine Service Co., 187 Ill.2d 567, 243 Ill.Dec. 77, 722 N.E.2d 1146 (2000) (ordering the Fifth District to vacate

Fictional by design: False; 

### First check: VERIFIED

The order directs the Fifth District to vacate and the circuit court to transfer from Madison to McHenry County.

Excerpt read: The Appellate Court, Fifth District, is directed to vacate; the circuit court is ordered to grant transfer from Madison County to McHenry County on forum non conveniens grounds.

- https://www.leagle.com/decision/20001868722ne2d114621785
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0217: Kranker v. Mitsubishi Motor Sales of America, Inc., 185 Ill. 2d 629 (1999) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Kranker v. Mitsubishi Motor Sales of America, Inc., 185 Ill.2d 629, 240 Ill.Dec. 325, 717 N.E.2d 418; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: m non conveniens motion to transfer venue and ordering the Madison County circuit court to transfer venue); Kranker v. Mitsubishi Motor Sales of America, Inc., 185 Ill.2d 629, 240 Ill.Dec. 325, 717 N.E.2d 418 (1999) (ordering the Cook County circuit cour

Fictional by design: False; 

### First check: VERIFIED

The order vacates Cook County’s denial of forum non conveniens transfer and directs a transfer order.

Excerpt read: The Circuit Court of Cook County denial of defendant’s forum non conveniens motion is vacated; the court is directed to enter an order transferring the case.

- https://www.leagle.com/decision/19991135717ne2d41821134
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0218: Beldner v. Tennessee Steel Haulers, Inc., 184 Ill. 2d 553 (1999) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Beldner v. Tennessee Steel Haulers, Inc., 184 Ill.2d 553, 238 Ill.Dec. 135, 710 N.E.2d 1237; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: 999) (ordering the Cook County circuit court to grant the defendant's forum non conveniens motion to transfer venue); Beldner v. Tennessee Steel Haulers, Inc., 184 Ill.2d 553, 238 Ill.Dec. 135, 710 N.E.2d 1237 (1999) (ordering the Fifth District to vacat

Fictional by design: False; 

### First check: VERIFIED

The order vacates the Fifth District judgment and directs Madison County to vacate denial and transfer to Williamson County.

Excerpt read: The Fifth District judgment is vacated; Madison County is directed to vacate denial and enter an order transferring venue to Williamson County.

- https://www.leagle.com/decision/19991947710ne2d123731864
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0219: Lawson v. Gateway Western Ry. Co., 184 Ill. 2d 558 (1999) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Lawson v. Gateway Western Ry. Co., 184 Ill.2d 558, 238 Ill.Dec. 134, 710 N.E.2d 1236; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: defendant's forum non conveniens motion to transfer venue and ordering the Madison County circuit court to transfer venue); Lawson v. Gateway Western Ry. Co., 184 Ill.2d 558, 238 Ill.Dec. 134, 710 N.E.2d 1236 (1999) (ordering the Fifth District to vacat

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Two Lawson supervisory orders share the same reporter page. The visible primary text confirms Fifth District vacatur and St. Clair County vacatur of a denial of forum non conveniens transfer, but Leagle truncates before the ultimate disposition. I cannot confirm the appendix’s assertion of a directed transfer from the visible order text.

Excerpt read: The Fifth District is directed to vacate its judgment; St. Clair County is directed to vacate denial of a motion to transfer on grounds of [text truncated].

- https://www.leagle.com/decision/19991946710ne2d123611868
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0220: Fitzgerald v. Jones, 181 Ill. 2d 570 (1998) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Fitzgerald v. Jones, 181 Ill.2d 570, 235 Ill.Dec. 666, 705 N.E.2d 849; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: denying the defendant's forum non conveniens motion to transfer venue and ordering the St. Clair County circuit court to transfer venue); Fitzgerald v. Jones, 181 Ill.2d 570, 235 Ill.Dec. 666, 705 N.E.2d 849 (1998) (ordering the Cook County circuit cour

Fictional by design: False; 

### First check: VERIFIED

The order directs Cook County to vacate denial and enter a transfer order on forum non conveniens grounds.

Excerpt read: Cook County is directed to vacate its denial of defendants’ motion to transfer venue on forum non conveniens grounds and to enter an order transferring venue.

- https://www.leagle.com/decision/19981554705ne2d84911530
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0221: Guest v. Detroit City Dairy, Inc., 177 Ill. 2d 569 (1998) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Guest v. Detroit City Dairy, Inc., 177 Ill.2d 569, 231 Ill.Dec. 747, 697 N.E.2d 301; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: 849 (1998) (ordering the Cook County circuit court to grant the defendant's forum non conveniens motion to transfer venue); Guest v. Detroit City Dairy, Inc., 177 Ill.2d 569, 231 Ill.Dec. 747, 697 N.E.2d 301 (1998) (same); Allen v. Illinois Power Co., 1

Fictional by design: False; 

### First check: MISCHARACTERIZED

The primary order directs Cook County to allow a motion to dismiss for forum non conveniens, while the Guerine appendix says it granted a motion to transfer venue. Dismissal and intrastate transfer are different procedural dispositions.

Excerpt read: Cook County is directed to vacate its denial of defendant’s motion to dismiss for forum non conveniens and enter an order allowing that motion to dismiss.

- https://www.leagle.com/decision/1998998697ne2d3013995
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: VERIFIED_MINOR_DEFECT

Overturns Sol's MISCHARACTERIZED. The April 1, 1998 order (697 N.E.2d 301, 177 Ill. 2d 569, 231 Ill. Dec. 747, No. 84816) directs the Cook County circuit court to vacate its October 2, 1997 order 'denying defendant's motion to dismiss for forum non conveniens, and to enter an order allowing defendant's motion to dismiss for forum non conveniens.' Guerine's '(same)' points back to Fitzgerald: 'ordering the Cook County circuit court to grant the defendant's forum non conveniens motion to transfer venue.' The court, the direction to grant, and the FNC basis are all correct. The motion is mislabeled 'transfer venue' when the order calls it a motion to dismiss. I did not independently confirm whether Guest was an interstate case; I read no underlying record. Current Rule 187(c)(2) treats dismissal as the interstate remedy, but I read only the current rule text (amended 2013 and 2017), not the 1998 version. Guerine's appendix reads as a stylized summary, not a precise motion-by-motion description: (1) every one of the roughly 30 entries uses the same phrase, 'forum non conveniens motion to transfer venue', including A.P. Green, whose own order describes a 'motion to dismiss or transfer'; (2) the body sentence that cites the appendix ('Since Peile, we have exercised our supervisory authority more than 30 times to transfer cases away from plaintiffs' chosen fora') counts reconsideration orders (Wakehouse, Popp) and an interlocutory-appeal order (A.P. Green) as instances of 'transfer', so the court is using 'transfer' loosely; (3) the appendix says 'ordering the Fifth District to vacate' even where the supreme court itself vacated the appellate judgment, and those rows were VERIFIED (Kinzler, Beldner). The official reporter text on CourtListener (764 N.E.2d at *64-*66) matches the attachment word for word, including the 'reconsider is order' typo, so these are the court's own words and not artifacts of the copy. House calibration: if the proposition the authority is cited for survives and a parenthetical detail is wrong, the row is VERIFIED_MINOR_DEFECT; MISCHARACTERIZED is reserved for a parenthetical that states a disposition the order does not contain or that is the opposite of it. An FNC dismissal also takes the case away from the plaintiff's chosen forum, so the order supports what the appendix cites it for. The 'transfer venue' label is a loose parenthetical detail, not a disposition the order lacks.

Excerpt read: 'Petition for leave to appeal denied. In the exercise of this Court's supervisory authority, the Circuit Court of Cook County, in case No. 96 L 14302, is directed to vacate its order of October 2, 1997, denying defendant's motion to dismiss for forum non conveniens, and to enter an order allowing defendant's motion to dismiss for forum non conveniens...'

- https://www.leagle.com/decision/1998998697ne2d3013995
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf
- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/7ae8a196-2a43-4484-9666-43098da60282/S_Ct_Rules_full.pdf

Model: claude-opus-5-5; reasoning effort: high (orchestration-configured).

## FNC-0222: Allen v. Illinois Power Co., 173 Ill. 2d 521 (1997) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Allen v. Illinois Power Co., 173 Ill.2d 521, 225 Ill.Dec. 391, 683 N.E.2d 894; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: iens motion to transfer venue); Guest v. Detroit City Dairy, Inc., 177 Ill.2d 569, 231 Ill.Dec. 747, 697 N.E.2d 301 (1998) (same); Allen v. Illinois Power Co., 173 Ill.2d 521, 225 Ill.Dec. 391, 683 N.E.2d 894 (1997) (ordering the St. Clair County circuit

Fictional by design: False; 

### First check: VERIFIED

The order directs St. Clair County to vacate denial and transfer venue under forum non conveniens.

Excerpt read: St. Clair County is directed to vacate denial of defendant’s motion to transfer venue on forum non conveniens grounds and enter an order transferring venue.

- https://www.leagle.com/decision/19971577683ne2d89411528
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0223: Grose v. Illinois Power Co., 169 Ill. 2d 566 (1996) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Grose v. Illinois Power Co., 169 Ill.2d 566, 220 Ill.Dec. 224, 672 N.E.2d 1236; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: d 894 (1997) (ordering the St. Clair County circuit court to grant the defendant's forum non conveniens motion to transfer venue); Grose v. Illinois Power Co., 169 Ill.2d 566, 220 Ill.Dec. 224, 672 N.E.2d 1236 (1996) (same); Kinzler v. Chicago & North We

Fictional by design: False; 

### First check: VERIFIED

The order directs St. Clair County to vacate denial and transfer venue on forum non conveniens grounds.

Excerpt read: St. Clair County is directed to vacate denial of a forum non conveniens transfer motion and enter an order transferring venue.

- https://www.leagle.com/decision/19961908672ne2d123631836
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0224: Kinzler v. Chicago & North Western Transportation Co., 169 Ill. 2d 569 (1996) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Kinzler v. Chicago & North Western Transportation Co., 169 Ill.2d 569, 220 Ill.Dec. 225, 672 N.E.2d 1237; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: er venue); Grose v. Illinois Power Co., 169 Ill.2d 566, 220 Ill.Dec. 224, 672 N.E.2d 1236 (1996) (same); Kinzler v. Chicago & North Western Transportation Co., 169 Ill.2d 569, 220 Ill.Dec. 225, 672 N.E.2d 1237 (1996) (ordering the Fifth District to vacat

Fictional by design: False; 

### First check: VERIFIED

The order vacates the Fifth District judgment and Madison County denial, then directs transfer from Madison to Bureau County.

Excerpt read: The Fifth District judgment and Madison County denial of transfer from Madison to Bureau County are vacated; Madison is directed to enter a transfer order.

- https://www.leagle.com/decision/19961909672ne2d123721834
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0225: Weicherding v. Southern Pacific Transportation Co., 169 Ill. 2d 590 (1996) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Weicherding v. Southern Pacific Transportation Co., 169 Ill.2d 590, 220 Ill.Dec. 224, 672 N.E.2d 1236; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: m non conveniens motion to transfer venue and ordering the Madison County circuit court to transfer venue); Weicherding v. Southern Pacific Transportation Co., 169 Ill.2d 590, 220 Ill.Dec. 224, 672 N.E.2d 1236 (1996) (ordering the St. Clair County circui

Fictional by design: False; 

### First check: VERIFIED

The order vacates St. Clair County denial and directs transfer to Marion County.

Excerpt read: St. Clair County denial of transfer to Marion County is vacated; it is directed to enter a transfer order.

- https://www.leagle.com/decision/19961908672ne2d123621837
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0226: McGeehon v. Burlington Northern R.R. Co., 168 Ill. 2d 596 (1996) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: McGeehon v. Burlington Northern R.R. Co., 168 Ill.2d 596, 219 Ill.Dec. 212, 670 N.E.2d 1100; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: (ordering the St. Clair County circuit court to grant the defendant's forum non conveniens motion to transfer venue); McGeehon v. Burlington Northern R.R. Co., 168 Ill.2d 596, 219 Ill.Dec. 212, 670 N.E.2d 1100 (1996) (ordering the Madison County circuit

Fictional by design: False; 

### First check: VERIFIED

The order vacates Madison County denial and directs transfer to Jefferson County.

Excerpt read: Madison County denial of transfer to Jefferson County is vacated; the court is directed to transfer to Jefferson County.

- https://www.leagle.com/decision/19961770670ne2d110041726
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0227: Beppler v. Illinois Central R.R. Co., 167 Ill. 2d 549 (1996) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Beppler v. Illinois Central R.R. Co., 167 Ill.2d 549, 216 Ill.Dec. 585, 665 N.E.2d 843; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: 1996) (ordering the Madison County circuit court to grant the defendant's forum non conveniens motion to transfer venue); Beppler v. Illinois Central R.R. Co., 167 Ill.2d 549, 216 Ill.Dec. 585, 665 N.E.2d 843 (1996) (ordering the Fifth District to vacate

Fictional by design: False; 

### First check: VERIFIED

The order vacates the Fifth District order and St. Clair County denial, and directs St. Clair County to transfer venue. The Leagle reproduction lacks the Ill. 2d and Illinois Decisions parallel cites but the N.E.2d citation and disposition match.

Excerpt read: The Fifth District order and St. Clair County denial of forum non conveniens transfer are vacated; St. Clair County is directed to enter an order transferring venue.

- https://www.leagle.com/decision/19961508665ne2d84311451
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0228: Uebinger v. Marathon Petroleum Co., 166 Ill. 2d 555 (1996) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Uebinger v. Marathon Petroleum Co., 166 Ill.2d 555, 215 Ill.Dec. 216, 662 N.E.2d 1356; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: fendant's forum non conveniens motion to transfer venue and ordering the St. Clair County circuit court to transfer venue); Uebinger v. Marathon Petroleum Co., 166 Ill.2d 555, 215 Ill.Dec. 216, 662 N.E.2d 1356 (1996) (ordering the Madison County circuit

Fictional by design: False; 

### First check: VERIFIED

The order vacates Madison County denial and directs transfer to Crawford County.

Excerpt read: Madison County is directed to vacate denial of a forum non conveniens transfer and enter an order transferring venue to Crawford County.

- https://www.leagle.com/decision/19962018662ne2d135611954
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0229: Eby v. Illinois Power Co., 164 Ill. 2d 561 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Eby v. Illinois Power Co., 164 Ill.2d 561, 212 Ill.Dec. 871, 658 N.E.2d 48; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: E.2d 1356 (1996) (ordering the Madison County circuit court to grant the defendant's forum non conveniens motion to transfer venue); Eby v. Illinois Power Co., 164 Ill.2d 561, 212 Ill.Dec. 871, 658 N.E.2d 48 (1995) (same); Peters v. Burlington Northern R

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The Guerine appendix identifies Eby at 164 Ill. 2d 561 / 658 N.E.2d 48, but I could not obtain that supervisory order text. Leagle’s 658 N.E.2d and 164 Ill.2d volume indexes did not return Eby, and targeted public search returned only citations to Guerine. CourtListener non-location alone is not treated as proof of fabrication.

Excerpt read: Only Guerine appendix wording was available; Eby order text not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf
- https://www.leagle.com/decisions/browse/series/volume/658%20n.e.2D
- https://www.leagle.com/decisions/browse/series/volume/164%20Ill.2d

### Second check: not required


## FNC-0230: Peters v. Burlington Northern R.R. Co., 163 Ill. 2d 585 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Peters v. Burlington Northern R.R. Co., 163 Ill.2d 585, 211 Ill.Dec. 534, 655 N.E.2d 917; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: ns motion to transfer venue); Eby v. Illinois Power Co., 164 Ill.2d 561, 212 Ill.Dec. 871, 658 N.E.2d 48 (1995) (same); Peters v. Burlington Northern R.R. Co., 163 Ill.2d 585, 211 Ill.Dec. 534, 655 N.E.2d 917 (1995) (same); Doe v. Terra Properties, Inc.,

Fictional by design: False; 

### First check: MISCHARACTERIZED

The primary order says Madison County denied a motion to dismiss on forum non conveniens grounds and directs the court to allow that motion. Guerine’s appendix calls it a motion to transfer venue.

Excerpt read: Madison County is directed to vacate denial of defendant’s motion to dismiss on the basis of forum non conveniens and enter an order allowing that motion.

- https://www.leagle.com/decision/19951572655ne2d91711532
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: VERIFIED_MINOR_DEFECT

Overturns Sol's MISCHARACTERIZED. The October 4, 1995 order (655 N.E.2d 917, 163 Ill. 2d 585, 211 Ill. Dec. 534, No. 79403) directs the Madison County circuit court to vacate its order in No. 94-L-381 'denying defendant's motion to dismiss the case on the basis of forum non conveniens and to enter an order allowing...'. Leagle's text stops there, so the object of 'allowing' is not on the page; Sol's 'allowing that motion' is an inference, though the natural one. Guerine's '(same)' (back through Eby to Uebinger) reads 'ordering the Madison County circuit court to grant the defendant's forum non conveniens motion to transfer venue.' The court, the vacatur of an FNC denial, and the direction to allow are correct. The motion type is mislabeled (dismiss, not transfer). I did not confirm whether Peters was interstate, and I read only the current text of Rule 187. Because of the truncation, the visible text cannot show that the disposition itself was mischaracterized; what it does show is a wrong motion label. Guerine's appendix reads as a stylized summary, not a precise motion-by-motion description: (1) every one of the roughly 30 entries uses the same phrase, 'forum non conveniens motion to transfer venue', including A.P. Green, whose own order describes a 'motion to dismiss or transfer'; (2) the body sentence that cites the appendix ('Since Peile, we have exercised our supervisory authority more than 30 times to transfer cases away from plaintiffs' chosen fora') counts reconsideration orders (Wakehouse, Popp) and an interlocutory-appeal order (A.P. Green) as instances of 'transfer', so the court is using 'transfer' loosely; (3) the appendix says 'ordering the Fifth District to vacate' even where the supreme court itself vacated the appellate judgment, and those rows were VERIFIED (Kinzler, Beldner). The official reporter text on CourtListener (764 N.E.2d at *64-*66) matches the attachment word for word, including the 'reconsider is order' typo, so these are the court's own words and not artifacts of the copy. House calibration: if the proposition the authority is cited for survives and a parenthetical detail is wrong, the row is VERIFIED_MINOR_DEFECT; MISCHARACTERIZED is reserved for a parenthetical that states a disposition the order does not contain or that is the opposite of it. The order supports the cited proposition, so the label error is a minor defect.

Excerpt read: 'In the exercise of this Court's supervisory authority, the Circuit Court of Madison County is directed to vacate its order in case No. 94-L-381 denying defendant's motion to dismiss the case on the basis of forum non conveniens and to enter an order allowing...' [truncated]

- https://www.leagle.com/decision/19951572655ne2d91711532
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf
- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/7ae8a196-2a43-4484-9666-43098da60282/S_Ct_Rules_full.pdf

Model: claude-opus-5-5; reasoning effort: high (orchestration-configured).

## FNC-0231: Doe v. Terra Properties, Inc., 163 Ill. 2d 552 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Doe v. Terra Properties, Inc., 163 Ill.2d 552, 211 Ill.Dec. 533, 655 N.E.2d 916; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: N.E.2d 48 (1995) (same); Peters v. Burlington Northern R.R. Co., 163 Ill.2d 585, 211 Ill.Dec. 534, 655 N.E.2d 917 (1995) (same); Doe v. Terra Properties, Inc., 163 Ill.2d 552, 211 Ill.Dec. 533, 655 N.E.2d 916 (1995) (same); Mosier v. Danz, 163 Ill.2d 563

Fictional by design: False; 

### First check: VERIFIED

The order directs Madison County to vacate denial and transfer venue to Clinton County.

Excerpt read: Madison County is directed to vacate denial of forum non conveniens transfer and enter an order transferring venue to Clinton County.

- https://www.leagle.com/decision/19951571655ne2d91621533
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0232: Mosier v. Danz, 163 Ill. 2d 563 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Mosier v. Danz, 163 Ill.2d 563, 211 Ill.Dec. 532, 655 N.E.2d 915; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: 211 Ill.Dec. 534, 655 N.E.2d 917 (1995) (same); Doe v. Terra Properties, Inc., 163 Ill.2d 552, 211 Ill.Dec. 533, 655 N.E.2d 916 (1995) (same); Mosier v. Danz, 163 Ill.2d 563, 211 Ill.Dec. 532, 655 N.E.2d 915 (1995) (ordering the Fifth District to vacate

Fictional by design: False; 

### First check: VERIFIED

The order vacates the Fifth District judgment and directs Madison County to grant a venue transfer on forum non conveniens grounds.

Excerpt read: The Fifth District judgment is vacated; Madison County is directed to vacate denial and enter an order transferring venue.

- https://www.leagle.com/decision/19951570655ne2d91541534
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0233: Harms v. Wal-Mart Stores, Inc., 162 Ill. 2d 567 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Harms v. Wal-Mart Stores, Inc., 162 Ill.2d 567, 209 Ill.Dec. 65, 650 N.E.2d 1038; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: the defendant's forum non conveniens motion to transfer venue and ordering the Madison County circuit court to transfer venue); Harms v. Wal-Mart Stores, Inc., 162 Ill.2d 567, 209 Ill.Dec. 65, 650 N.E.2d 1038 (1995) (ordering the Fifth District to vacate

Fictional by design: False; 

### First check: VERIFIED

The order vacates the Fifth District judgment and St. Clair County denial, and directs a venue transfer.

Excerpt read: The Fifth District judgment and St. Clair County denial of forum non conveniens transfer are vacated; the circuit court is directed to enter a transfer order.

- https://www.leagle.com/decision/19951688650ne2d103821623
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0234: Popp v. Lincoln Electric Co., 162 Ill. 2d 580 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Popp v. Lincoln Electric Co., 162 Ill.2d 580, 208 Ill.Dec. 757, 650 N.E.2d 214; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: the defendant's forum non conveniens motion to transfer venue and ordering the St. Clair County circuit court to transfer venue); Popp v. Lincoln Electric Co., 162 Ill.2d 580, 208 Ill.Dec. 757, 650 N.E.2d 214 (1995) (ordering the First District to recons

Fictional by design: False; 

### First check: MISCHARACTERIZED

The primary order vacates the First District judgment but directs the Cook County circuit court to reconsider its denial of a motion to dismiss in light of Peile. Guerine instead says the First District itself was ordered to reconsider its order affirming the trial court.

Excerpt read: The First District judgment is vacated and the Circuit Court of Cook County is directed to reconsider its denial of defendants’ motions to dismiss under forum non conveniens.

- https://www.leagle.com/decision/1995864650ne2d2142858
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: VERIFIED_MINOR_DEFECT

Overturns Sol's MISCHARACTERIZED. This is the closest call of the nine. The June 1, 1995 order (650 N.E.2d 214, 162 Ill. 2d 580, 208 Ill. Dec. 757, No. 78783) says the judgment of the First District in No. 1-94-4093 'is VACATED and the Circuit Court of Cook County is directed to reconsider its order in case No. 94-L-4145 denying defendant's motions to dismiss the case under the doctrine of forum non conveniens, in light of Peile v. Skelgas.' Guerine says 'ordering the First District to reconsider [its] order affirming the trial court's denial of the defendant's forum non conveniens motion to transfer venue.' The parenthetical gets two things wrong and asserts a third that the order text neither confirms nor denies. It names the wrong court as the one told to reconsider (the order vacates the First District's judgment and sends reconsideration to the circuit court). It calls the motion a transfer motion when the order says motions to dismiss. And it calls the First District's ruling an 'affirmance', which the order text does not say; that point is unverified, not shown false. I weighed this against the house examples. The parenthetical does not assert the opposite of the order or an unrelated holding, as in the Pruett and Emlee rows. Its substance is correct: the supreme court used supervisory authority to set aside the appellate disposition and send the FNC denial back for reconsideration in light of Peile. The errors concern which court reconsiders and what the appellate ruling was called, which is closer to the 'FRSA, not SOX' type of minor detail error. Guerine's appendix reads as a stylized summary, not a precise motion-by-motion description: (1) every one of the roughly 30 entries uses the same phrase, 'forum non conveniens motion to transfer venue', including A.P. Green, whose own order describes a 'motion to dismiss or transfer'; (2) the body sentence that cites the appendix ('Since Peile, we have exercised our supervisory authority more than 30 times to transfer cases away from plaintiffs' chosen fora') counts reconsideration orders (Wakehouse, Popp) and an interlocutory-appeal order (A.P. Green) as instances of 'transfer', so the court is using 'transfer' loosely; (3) the appendix says 'ordering the Fifth District to vacate' even where the supreme court itself vacated the appellate judgment, and those rows were VERIFIED (Kinzler, Beldner). The official reporter text on CourtListener (764 N.E.2d at *64-*66) matches the attachment word for word, including the 'reconsider is order' typo, so these are the court's own words and not artifacts of the copy. House calibration: if the proposition the authority is cited for survives and a parenthetical detail is wrong, the row is VERIFIED_MINOR_DEFECT; MISCHARACTERIZED is reserved for a parenthetical that states a disposition the order does not contain or that is the opposite of it. A stricter reviewer who treats naming the wrong court as a misstated disposition could reasonably keep MISCHARACTERIZED. I rate it minor because the cited proposition survives intact.

Excerpt read: 'Petition for leave to appeal denied. In the exercise of this Court's supervisory authority, the judgment of the Appellate Court, First District, in case No. 1-94-4093, is VACATED and the Circuit Court of Cook County is directed to reconsider its order in case No. 94-L-4145 denying defendant's motions to dismiss the case under the doctrine of forum non conveniens, in light of Peile v. Skelgas (1994), 163 Ill.2d 323, ...' [truncated]

- https://www.leagle.com/decision/1995864650ne2d2142858
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

Model: claude-opus-5-5; reasoning effort: high (orchestration-configured).

## FNC-0235: Ferris v. Southern Pacific Transportation Co., 162 Ill. 2d 566 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Ferris v. Southern Pacific Transportation Co., 162 Ill.2d 566, 208 Ill.Dec. 848, 650 N.E.2d 542; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: r is order affirming the trial court's denial of the defendant's forum non conveniens motion to transfer venue); Ferris v. Southern Pacific Transportation Co., 162 Ill.2d 566, 208 Ill.Dec. 848, 650 N.E.2d 542 (1995) (ordering the Madison County circuit c

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

The real Ferris supervisory order and its Ill. 2d / Ill. Dec. parallels match, and its transfer disposition is supported, but Guerine gives 650 N.E.2d 542. The reproduced primary reporter entry is at 650 N.E.2d 544. This is an incorrect parallel reporter page, not evidence the case is fabricated.

Excerpt read: Ferris v. Southern Pacific Transportation Co., 162 Ill. 2d 566, 208 Ill. Dec. 848, 650 N.E.2d 544: Madison County is directed to vacate denial and transfer venue to Macoupin County.

- https://www.leagle.com/decision/19951194650ne2d54411165
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: WRONG_CITATION_REAL_CASE

I tried to downgrade this to VERIFIED_MINOR_DEFECT and could not; Sol's status stands. The June 1, 1995 Ferris order is real. It sits at 650 N.E.2d 544 with 162 Ill. 2d 566 and 208 Ill. Dec. 848, and it directs Madison County to vacate its denial of the 'motion to transfer venue on the basis of forum non conveniens' and to transfer venue to Macoupin [County], which matches the appendix's disposition. Guerine's 650 N.E.2d 542 is wrong. My check does not rely on Leagle's URL encoding. Leagle's 650 N.E.2d volume index lists no entry beginning at page 542 or 543. Zurich Insurance Co. v. Baxter International (162 Ill. 2d 582) and People v. Schwickert (162 Ill. 2d 577) are both at 650 N.E.2d 541 / 208 Ill. Dec. 847, and Ferris and People v. Meyers are both at 650 N.E.2d 544 / 208 Ill. Dec. 848. So Guerine's correct Ill. Dec. 848 parallel itself corresponds to N.E.2d 544. The official Guerine text on CourtListener also prints 542, so the error is in the published opinion. In this audit, a wrong reporter location for a real case is WRONG_CITATION_REAL_CASE (compare KEHOE-072). It is at the mild end because the Ill. 2d and Ill. Dec. cites are correct. Residual uncertainty: I cannot rule out that pages 542-43 hold a petition-for-leave-to-appeal-denied table listing Ferris; the index shows no entry there.

Excerpt read: Ferris: '650 N.E.2d 544 (1995) / 162 Ill.2d 566 / 208 Ill.Dec. 848 ... the Circuit Court of Madison County is directed to vacate its order in case No. 94-L-731 denying defendant's motion to transfer venue on the basis of forum non conveniens and to enter an order transferring venue to Macoupin...' [truncated]. Zurich: '650 N.E.2d 541 (1995) / 162 Ill.2d 582 / 208 Ill.Dec. 847'. Schwickert: '650 N.E.2d 541 (1995) / 162 Ill.2d 577 / 208 Ill.Dec. 847'. Meyers: '650 N.E.2d 544 (1995) / 162 Ill.2d 576 / 208 Ill.Dec. 848'. Guerine (CourtListener): 'Ferris v. Southern Pacific Transportation Co., 162 Ill.2d 566, 208 Ill.Dec. 848, 650 N.E.2d 542 (1995)'.

- https://www.leagle.com/decision/19951194650ne2d54411165
- https://www.leagle.com/decisions/browse/series/volume/650%20N.E.2d
- https://www.leagle.com/decision/19951191650ne2d54111164
- https://www.leagle.com/decision/19951191650ne2d54121163
- https://www.leagle.com/decision/19951194650ne2d54421164
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

Model: claude-opus-5-5; reasoning effort: high (orchestration-configured).

## FNC-0236: Mayse v. Servicemaster Co. Ltd. Partnership, 159 Ill. 2d 569 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 9.

Authority type: case; as written: Mayse v. Servicemaster Co. Ltd. Partnership, 159 Ill.2d 569; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: ordering the Madison County circuit court to grant the defendant's forum non conveniens motion to transfer venue); Mayse v. Servicemaster Co. Ltd. Partnership, 159 Ill.2d 569 (1995) (ordering the Fifth District to vacate its order denying the defendant's

Fictional by design: False; 

### First check: VERIFIED

The order vacates the Fifth District judgment and directs St. Clair County to vacate denial of a forum non conveniens transfer motion and allow it. The reproduction truncates the final object after “allowing”; exact destination was not independently read.

Excerpt read: The Fifth District judgment is vacated; St. Clair County is directed to vacate denial of defendant’s transfer motion and enter an order allowing [visible text ends].

- https://www.leagle.com/decision/19951605645ne2d96011519
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0237: Strube v. CLC of America, Inc., 159 Ill. 2d 580 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 10.

Authority type: case; as written: Strube v. CLC of America, Inc., 159 Ill.2d 580, 206 Ill.Dec. 201, 645 N.E.2d 206; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: venue and ordering the St. Clair County circuit court to transfer venue); Strube v. CLC of America, Inc., 159 Ill.2d 580, 206 Ill.Dec. 201, 645 N.E.2d 206 (1995) (ordering the Fifth District to vacate

Fictional by design: False; 

### First check: VERIFIED

The order vacates the Fifth District judgment and directs Madison County to vacate denial of a forum non conveniens transfer motion and allow it. The reproduction truncates the final clause.

Excerpt read: The Fifth District judgment is vacated; Madison County is directed to vacate denial of defendant’s transfer motion and enter an order allowing [visible text ends].

- https://www.leagle.com/decision/1995851645ne2d2061846
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0238: Rogers v. Gateway Western Ry. Co., 159 Ill. 2d 579 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 10.

Authority type: case; as written: Rogers v. Gateway Western Ry. Co., 159 Ill.2d 579, 206 Ill.Dec. 201, 645 N.E.2d 206; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: defendant's forum non conveniens motion to transfer venue and ordering the Madison County circuit court to transfer venue); Rogers v. Gateway Western Ry. Co., 159 Ill.2d 579, 206 Ill.Dec. 201, 645 N.E.2d 206 (1995) (ordering the Fifth District to vacate

Fictional by design: False; 

### First check: MISCHARACTERIZED

The primary order vacates the Fifth District and St. Clair denial, then remands for a hearing to determine the appropriate trial county. Guerine says it ordered St. Clair County to transfer venue outright.

Excerpt read: The denial is vacated and the case is remanded to the circuit court for a hearing to determine the appropriate county in which to try the case.

- https://www.leagle.com/decision/1995851645ne2d2062845
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: VERIFIED_MINOR_DEFECT

Overturns Sol's MISCHARACTERIZED. The February 1, 1995 order (645 N.E.2d 206, 159 Ill. 2d 579, 206 Ill. Dec. 201, No. 76944) vacates the Fifth District's judgment in No. 5-92-0577. It also vacates the St. Clair County order 'denying defendant's motion to transfer the case on the basis of forum non conveniens' and remands 'for a hearing to determine the appropriate county in which to try this case.' The disposition sentence is complete before Leagle's cutoff ('Harrison II,...'). Guerine says 'ordering the Fifth District to vacate its order denying the defendant's forum non conveniens motion to transfer venue and ordering the St. Clair County circuit court to transfer venue.' The motion type (transfer) and the vacatur of the denial are correct. 'Ordering the Fifth District to vacate', where the supreme court itself vacated, is the appendix's standard phrasing, and the same phrasing was accepted as VERIFIED for Kinzler and Beldner. The real defect is that the parenthetical says the court ordered an outright transfer, while the order remanded for a hearing on the appropriate county and named no transferee. That overstates the order by leaving out the hearing step; it does not invent a disposition. I do not assume what the hearing produced. Guerine's appendix reads as a stylized summary, not a precise motion-by-motion description: (1) every one of the roughly 30 entries uses the same phrase, 'forum non conveniens motion to transfer venue', including A.P. Green, whose own order describes a 'motion to dismiss or transfer'; (2) the body sentence that cites the appendix ('Since Peile, we have exercised our supervisory authority more than 30 times to transfer cases away from plaintiffs' chosen fora') counts reconsideration orders (Wakehouse, Popp) and an interlocutory-appeal order (A.P. Green) as instances of 'transfer', so the court is using 'transfer' loosely; (3) the appendix says 'ordering the Fifth District to vacate' even where the supreme court itself vacated the appellate judgment, and those rows were VERIFIED (Kinzler, Beldner). The official reporter text on CourtListener (764 N.E.2d at *64-*66) matches the attachment word for word, including the 'reconsider is order' typo, so these are the court's own words and not artifacts of the copy. House calibration: if the proposition the authority is cited for survives and a parenthetical detail is wrong, the row is VERIFIED_MINOR_DEFECT; MISCHARACTERIZED is reserved for a parenthetical that states a disposition the order does not contain or that is the opposite of it. The order supports the cited proposition, since it vacated a denial of FNC transfer that had kept the case in the plaintiff's chosen county, so this is a minor defect.

Excerpt read: 'In the exercise of this Court's supervisory authority, the judgment of the Appellate Court, Fifth District, No. 5-92-0577, is VACATED. It is further ordered that the order of the Circuit Court of St. Clair County in case No. 91-L-1340 denying defendant's motion to transfer the case on the basis of forum non conveniens is VACATED, and this case is REMANDED to the circuit court for a hearing to determine the appropriate county in which to try this case. Harrison II,...' [truncated]

- https://www.leagle.com/decision/1995851645ne2d2062845
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

Model: claude-opus-5-5; reasoning effort: high (orchestration-configured).

## FNC-0239: Swartzlander v. Illinois Central R.R. Co., 159 Ill. 2d 581 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 10.

Authority type: case; as written: Swartzlander v. Illinois Central R.R. Co., 159 Ill.2d 581, 206 Ill.Dec. 710, 645 N.E.2d 962; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: 's forum non conveniens motion to transfer venue and ordering the St. Clair County circuit court to transfer venue); Swartzlander v. Illinois Central R.R. Co., 159 Ill.2d 581, 206 Ill.Dec. 710, 645 N.E.2d 962 (1995) (ordering the Fifth District to vacate

Fictional by design: False; 

### First check: VERIFIED

The order vacates the Fifth District and Madison denial and transfers the case to Randolph County.

Excerpt read: The Fifth District judgment and Madison denial are vacated; the case is transferred to Randolph County.

- https://www.leagle.com/decision/19951607645ne2d96231515
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0240: Carpenter v. Strausberg, 159 Ill. 2d 564 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 10.

Authority type: case; as written: Carpenter v. Strausberg, 159 Ill.2d 564, 206 Ill.Dec. 711, 645 N.E.2d 963; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: enying the defendant's forum non conveniens motion to transfer venue and ordering the Madison County circuit court to transfer venue); Carpenter v. Strausberg, 159 Ill.2d 564, 206 Ill.Dec. 711, 645 N.E.2d 963 (1995) (ordering the First District appellate

Fictional by design: False; 

### First check: VERIFIED

The order vacates the First District and Cook denial and transfers the case to Will County.

Excerpt read: The First District judgment and Cook denial are vacated; the case is transferred to Will County.

- https://www.leagle.com/decision/19951608645ne2d96341511
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0241: Wojtonik v. Illinois Central R.R., 159 Ill. 2d 583 (1995) (supervisory order)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 10.

Authority type: case; as written: Wojtonik v. Illinois Central R.R., 159 Ill.2d 583, 206 Ill.Dec. 202, 645 N.E.2d 207; pincite: .

Cited for: Listed in Guerine appendix as one of 30+ supervisory orders transferring cases away from plaintiffs' chosen fora

Quotes: []

Context: the defendant's forum non conveniens motion to transfer venue and ordering the Cook County circuit court to transfer venue); Wojtonik v. Illinois Central R.R., 159 Ill.2d 583, 206 Ill.Dec. 202, 645 N.E.2d 207 (1995) (ordering the Fifth District to vacate

Fictional by design: False; 

### First check: VERIFIED

The order vacates the Fifth District judgment and directs Madison County to vacate denial of a forum non conveniens transfer motion and allow it. The reproduction truncates the final clause.

Excerpt read: The Fifth District judgment is vacated; Madison County is directed to vacate denial of defendant’s transfer motion and enter an order allowing [visible text ends].

- https://www.leagle.com/decision/1995852645ne2d2071844
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0242: Ill. S. Ct. R. 383

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 10.

Authority type: court_rule; as written: Supreme Court Rule 383 (188 Ill.2d R. 383); pincite: .

Cited for: This list does not include the innumerable cases in which the defendant has filed a motion for a supervisory order from this court directing the trial court to transfer the case. See

Quotes: []

Context: ude the innumerable cases in which the defendant has filed a motion for a supervisory order from this court directing the trial court to transfer the case. See 188 Ill.2d R. 383. Justice FITZGERALD delivered the opinion of the court

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage. Cited as the 188 Ill. 2d edition; that edition was not read.

Excerpt read: 'Rule 383. Motions for Supervisory Orders'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0243: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 1.

Authority type: case; as written: 207 Ill.2d 167; pincite: .

Cited for: This court then entered a supervisory order directing the appellate court to vacate and reconsider its judgment in light of Dawdy v. Union Pacific R.R. Co.,

Quotes: []

Context: l. This court then entered a supervisory order directing the appellate court to vacate and reconsider its judgment in light of Dawdy v. Union Pacific R.R. Co., 207 Ill.2d 167, 278 Ill.Dec. 92, 797 N.E.2d 687 (2003), and First American Bank v. Guerine, 19

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Lead opinion (CourtListener 9819104) read in full, e.g. 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County' [207 Ill. 2d at 178].

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0244: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 1.

Authority type: case; as written: 198 Ill.2d 511; pincite: .

Cited for: 92, 797 N.E.2d 687 (2003), and First American Bank v. Guerine,

Quotes: []

Context: econsider its judgment in light of Dawdy v. Union Pacific R.R. Co., 207 Ill.2d 167, 278 Ill.Dec. 92, 797 N.E.2d 687 (2003), and First American Bank v. Guerine, 198 Ill.2d 511, 261 Ill.Dec. 763, 764 N.E.2d 54 (2002). Upon reconsideration, the appellate co

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Ill. Reports text (CourtListener 3134965): 'First American Bank, as executor of Angel's estate ...'; N.E.2d text (2056494) caption 'FIRST NATIONAL BANK et al., Appellants, v. Richard GUERINE et al.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0245: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 1.

Authority type: case; as written: 354 Ill.App.3d 1103; pincite: .

Cited for: Upon reconsideration, the appellate court affirmed the circuit court's denial of defendants' motion to transfer.

Quotes: []

Context: d 511, 261 Ill.Dec. 763, 764 N.E.2d 54 (2002). Upon reconsideration, the appellate court affirmed the circuit court's denial of defendants' motion to transfer. 354 Ill.App.3d 1103, 290 Ill.Dec. 895, 822 N.E.2d 480. We allowed defendants' petition for leave to

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0246: Ill. S. Ct. R. 315

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 1.

Authority type: court_rule; as written: Supreme Court Rule 315 (177 Ill.2d R. 315); pincite: .

Cited for: 895, 822 N.E.2d 480. We allowed defendants' petition for leave to appeal (

Quotes: []

Context: t court's denial of defendants' motion to transfer. 354 Ill.App.3d 1103, 290 Ill.Dec. 895, 822 N.E.2d 480. We allowed defendants' petition for leave to appeal (177 Ill.2d R. 315). We also allowed the Illinois Trial Lawyers Association leave to file a brief

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage. Cited as the 177 Ill. 2d edition; that edition was not read.

Excerpt read: 'Rule 315. Leave to Appeal From the Appellate Court to the Supreme Court'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0247: Ill. S. Ct. R. 345(a)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 1.

Authority type: court_rule; as written: Supreme Court Rule 345(a (155 Ill.2d R. 345(a); pincite: .

Cited for: We also allowed the Illinois Trial Lawyers Association leave to file a brief as amicus curiae in support of plaintiff.

Quotes: []

Context: for leave to appeal (177 Ill.2d R. 315). We also allowed the Illinois Trial Lawyers Association leave to file a brief as amicus curiae in support of plaintiff. 155 Ill.2d R. 345(a). We now affirm. I. BACKGROUND On July 27, 2001, Gerald Langenhorst, a lifetime

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage. Cited as the 155 Ill. 2d edition; that edition was not read.

Excerpt read: 'Rule 345. Briefs Amicus Curiae (a) Leave or Request of Court Necessary. A brief amicus curiae may be filed only by leave of the court ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0248: 92 Ill. Adm. Code 1535.205, 1535.300

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 2.

Authority type: regulation; as written: 92 Adm.Code §§ 1535.300, 1535.205; pincite: .

Cited for: h needed to be cut to bring the crossing into compliance with the Administrative Code, “which requires the railroad right of way to be kept reasonably clear of brush, shrubbery, trees, weeds, crops, etc. for a distance of 500 feet each way from the crossing.”

Quotes: []

Context: es the railroad right of way to be kept reasonably clear of brush, shrubbery, trees, weeds, crops, etc. for a distance of 500 feet each way from the crossing.” 92 Adm.Code §§ 1535.300, 1535.205(2003). Stead advised Ellis to notify his office in writing when the corrective

Fictional by design: False; 

### First check: VERIFIED

Current JCAR text read; the 2003 version cited was not read (Part amended effective Dec. 15, 2005), but the quoted 500-foot clearance requirement and crossbuck provisions match.

Excerpt read: 1535.205: 'Every railroad shall keep its right-of-way adjacent to its tracks reasonably clear of brush, shrubbery, trees, weeds, crops ... for a distance of at least five hundred feet each way from every grade crossing ...'; 1535.300 'Crossbuck Signs' (reflective material on back of each blade)

- https://www.ilga.gov/agencies/JCAR/EntirePart?titlepart=09201535

### Second check: not required


## FNC-0249: Ill. S. Ct. R. 306(a)(2)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: court_rule; as written: Supreme Court Rule 306(a (166 Ill.2d R. 306(a); pincite: .

Cited for: On August 21, 2002, the appellate court denied defendants' petition to appeal pursuant to Supreme Court Rule 306(a)(2) (

Quotes: []

Context: n the doctrine of forum non conveniens. On August 21, 2002, the appellate court denied defendants' petition to appeal pursuant to Supreme Court Rule 306(a)(2) (166 Ill.2d R. 306(a)(2)). On October 7, 2003, this court denied defendants' petition for leave to a

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage.

Excerpt read: '(2) from an order of the circuit court allowing or denying a motion to dismiss on the grounds of forum non conveniens, or ... a motion to transfer a case to another county within this State on such grounds'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0250: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 207 Ill.2d 167; pincite: .

Cited for: On October 7, 2003, this court denied defendants' petition for leave to appeal and issued a supervisory order directing the appellate court to vacate its judgment and to reconsider its judgment in light of Dawdy v. Union Pacific R.R. Co.,

Quotes: []

Context: and issued a supervisory order directing the appellate court to vacate its judgment and to reconsider its judgment in light of Dawdy v. Union Pacific R.R. Co., 207 Ill.2d 167, 278 Ill.Dec. 92, 797 N.E.2d 687 (2003), and First American Bank v. Guerine, 19

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Lead opinion (CourtListener 9819104) read in full, e.g. 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County' [207 Ill. 2d at 178].

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0251: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 198 Ill.2d 511; pincite: .

Cited for: 92, 797 N.E.2d 687 (2003), and First American Bank v. Guerine,

Quotes: []

Context: econsider its judgment in light of Dawdy v. Union Pacific R.R. Co., 207 Ill.2d 167, 278 Ill.Dec. 92, 797 N.E.2d 687 (2003), and First American Bank v. Guerine, 198 Ill.2d 511, 261 Ill.Dec. 763, 764 N.E.2d 54 (2002). See Langenhorst v. Norfolk Southern Ry

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Ill. Reports text (CourtListener 3134965): 'First American Bank, as executor of Angel's estate ...'; N.E.2d text (2056494) caption 'FIRST NATIONAL BANK et al., Appellants, v. Richard GUERINE et al.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0252: Langenhorst v. Norfolk Southern Ry. Co., 205 Ill. 2d 586, 796 N.E.2d 1053 (2003) (table supervisory order)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 205 Ill.2d 586; pincite: .

Cited for: 763, 764 N.E.2d 54 (2002). See Langenhorst v. Norfolk Southern Ry. Co.,

Quotes: []

Context: 797 N.E.2d 687 (2003), and First American Bank v. Guerine, 198 Ill.2d 511, 261 Ill.Dec. 763, 764 N.E.2d 54 (2002). See Langenhorst v. Norfolk Southern Ry. Co., 205 Ill.2d 586, 277 Ill.Dec. 687, 796 N.E.2d 1053 (2003) (table). Upon reconsideration, the ap

Fictional by design: False; 

### First check: VERIFIED

Supervisory order located on CourtListener, dated Oct. 7, 2003, directing reconsideration in light of Dawdy and Guerine.

Excerpt read: Order text cites 'Dawdy v. Union Pacific R.R. Co. ... and First American Bank v. Guerine, 198 Ill.2d 511'; dated 2003-10-07.

- https://www.courtlistener.com/opinion/2150143/langenhorst-v-norfolk-southern-railway-company/

### Second check: not required


## FNC-0253: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 354 Ill.App.3d 1103; pincite: .

Cited for: Upon reconsideration, the appellate court affirmed the circuit court's denial of defendants' motion to transfer.

Quotes: []

Context: Ill.Dec. 687, 796 N.E.2d 1053 (2003) (table). Upon reconsideration, the appellate court affirmed the circuit court's denial of defendants' motion to transfer. 354 Ill.App.3d 1103, 290 Ill.Dec. 895, 822 N.E.2d 480. After reviewing Guerine and Dawdy, the appel

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0254: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 354 Ill.App.3d at 1122; pincite: 1122.

Cited for: Clair County did not abuse its discretion in denying defendants' forum non conveniens motion.

Quotes: []

Context: d private interest factors and held that the circuit court of St. Clair County did not abuse its discretion in denying defendants' forum non conveniens motion. 354 Ill.App.3d at 1122, 290 Ill.Dec. 895, 822 N.E.2d 480. The appellate court reasoned that a trial in

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0255: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 354 Ill.App.3d at 1116-17; pincite: 1116-17.

Cited for: Clair County courthouse, blocks away from the parties' attorneys' offices, would tend to make trial easier, more expeditious, and less expensive for the clients.

Quotes: []

Context: air County courthouse, blocks away from the parties' attorneys' offices, would tend to make trial easier, more expeditious, and less expensive for the clients. 354 Ill.App.3d at 1116-17, 290 Ill.Dec. 895, 822 N.E.2d 480. The appellate court also reasoned that even

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0256: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 354 Ill.App.3d at 1117; pincite: 1117.

Cited for: Clair County by virtue of doing business in that county, transfer to Clinton County would not find the litigation in the resident county of any of the other defendants.

Quotes: []

Context: nty by virtue of doing business in that county, transfer to Clinton County would not find the litigation in the resident county of any of the other defendants. 354 Ill.App.3d at 1117, 290 Ill.Dec. 895, 822 N.E.2d 480. The appellate court also examined witness co

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0257: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 354 Ill.App.3d at 1117-18; pincite: 1117-18.

Cited for: The appellate court also examined witness convenience and determined that any inconvenience the plaintiff's chosen forum presents is minuscule.

Quotes: []

Context: 822 N.E.2d 480. The appellate court also examined witness convenience and determined that any inconvenience the plaintiff's chosen forum presents is minuscule. 354 Ill.App.3d at 1117-18, 290 Ill.Dec. 895, 822 N.E.2d 480. It noted that the parties expected the plain

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0258: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 354 Ill.App.3d at 1119; pincite: 1119.

Cited for: It noted that the parties expected the plaintiff's investigator to give extensive testimony about his investigation of the accident scene immediately after the crash.

Quotes: []

Context: d that the parties expected the plaintiff's investigator to give extensive testimony about his investigation of the accident scene immediately after the crash. 354 Ill.App.3d at 1119, 290 Ill.Dec. 895, 822 N.E.2d 480. Due to changes in the railroad crossing, the

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0259: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 354 Ill.App.3d at 1119-20; pincite: 1119-20.

Cited for: Clair County border that travel to the accident scene would offer little inconvenience or expense.

Quotes: []

Context: were appropriate, the accident occurred so close to the St. Clair County border that travel to the accident scene would offer little inconvenience or expense. 354 Ill.App.3d at 1119-20, 290 Ill.Dec. 895, 822 N.E.2d 480. Further, the appellate court reasoned, none

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0260: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 354 Ill.App.3d at 1120; pincite: 1120.

Cited for: Further, the appellate court reasoned, none of the doctors reside in Clinton County.

Quotes: []

Context: e or expense. 354 Ill.App.3d at 1119-20, 290 Ill.Dec. 895, 822 N.E.2d 480. Further, the appellate court reasoned, none of the doctors reside in Clinton County. 354 Ill.App.3d at 1120, 290 Ill.Dec. 895, 822 N.E.2d 480. The appellate court determined that there wa

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0261: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 4.

Authority type: case; as written: 354 Ill.App.3d at 1121; pincite: 1121.

Cited for: Clair and Clinton Counties, and that it did not raise a concern over St. Clair County court congestion.

Quotes: []

Context: ifference in disposing of major civil cases between St. Clair and Clinton Counties, and that it did not raise a concern over St. Clair County court congestion. 354 Ill.App.3d at 1121, 290 Ill.Dec. 895, 822 N.E.2d 480. It was noted that the Norfolk line passing t

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0262: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: case; as written: 354 Ill.App.3d at 1122; pincite: 1122.

Cited for:  site, and the appellate court concluded that the local public interest was not limited to Clinton County residents.

Quotes: []

Context: site, and the appellate court concluded that the local public interest was not limited to Clinton County residents. 354 Ill.App.3d at 1122, 290 Ill.Dec. 895, 822 N.E.2d 480. Accordingly, the appellate court determined

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0263: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: case; as written: 354 Ill.App.3d at 1122; pincite: 1122.

Cited for: Clair County residents to serve on a jury that will decide the issues raised by this railroad accident case.

Quotes: []

Context: late court determined that it would not burden St. Clair County residents to serve on a jury that will decide the issues raised by this railroad accident case. 354 Ill.App.3d at 1122, 290 Ill.Dec. 895, 822 N.E.2d 480. Thus, the appellate court held that the circ

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0264: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: case; as written: 354 Ill.App.3d at 1122; pincite: 1122.

Cited for: Clair County did not abuse its discretion in deciding that the convenience factors do not strongly favor a transfer to Clinton County.

Quotes: []

Context: the circuit court of St. Clair County did not abuse its discretion in deciding that the convenience factors do not strongly favor a transfer to Clinton County. 354 Ill.App.3d at 1122, 290 Ill.Dec. 895, 822 N.E.2d 480. We allowed defendants' petition for leave to

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0265: Ill. S. Ct. R. 315

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: court_rule; as written: Supreme Court Rule 315 (177 Ill.2d R. 315); pincite: .

Cited for: 895, 822 N.E.2d 480. We allowed defendants' petition for leave to appeal (

Quotes: []

Context: not strongly favor a transfer to Clinton County. 354 Ill.App.3d at 1122, 290 Ill.Dec. 895, 822 N.E.2d 480. We allowed defendants' petition for leave to appeal (177 Ill.2d R. 315). We allowed the Illinois Trial Lawyers Association leave to file a brief as am

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage. Cited as the 177 Ill. 2d edition; that edition was not read.

Excerpt read: 'Rule 315. Leave to Appeal From the Appellate Court to the Supreme Court'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0266: Ill. S. Ct. R. 345(a)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: court_rule; as written: Supreme Court Rule 345(a (155 Ill.2d R. 345(a); pincite: .

Cited for: We allowed the Illinois Trial Lawyers Association leave to file a brief as amicus curiae in support of plaintiff.

Quotes: []

Context: tion for leave to appeal (177 Ill.2d R. 315). We allowed the Illinois Trial Lawyers Association leave to file a brief as amicus curiae in support of plaintiff. 155 Ill.2d R. 345(a). II. ANALYSIS The venue statute, section 2-101 of the Code of Civil Procedure,

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage. Cited as the 155 Ill. 2d edition; that edition was not read.

Excerpt read: 'Rule 345. Briefs Amicus Curiae (a) Leave or Request of Court Necessary. A brief amicus curiae may be filed only by leave of the court ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0267: 735 ILCS 5/2-101 (venue)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: statute; as written: 735 ILCS 5/2-101 (West 2000); pincite: .

Cited for: se for the purpose of obtaining a judgment against him or her and not solely for the purpose of fixing venue in that county, or (2) in the county in which the transaction or some part thereof occurred out of which the cause of action arose.” (Emphasis added.)

Quotes: []

Context: ng venue in that county, or (2) in the county in which the transaction or some part thereof occurred out of which the cause of action arose.” (Emphasis added.) 735 ILCS 5/2- 101 (West 2000). This court has recognized that “[t]he Illinois venue statute i

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session. (The opinion cites an earlier West edition; current text read, provision unchanged in substance.)

Excerpt read: 'every action must be commenced (1) in the county of residence of any defendant who is joined in good faith ... or (2) in the county in which the transaction or some part thereof occurred out of which the cause of action arose.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073500050K2-101.htm

### Second check: not required


## FNC-0268: Baltimore & Ohio R.R. Co. v. Mosele, 67 Ill. 2d 321, 368 N.E.2d 88 (1977)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: case; as written: 67 Ill.2d 321, 328; pincite: 328.

Cited for: t the action will be brought either in a location convenient to the defendant, by providing for venue in the county of residence, or convenient to potential witnesses by allowing for venue where the cause of action arose.” Baltimore & Ohio R.R. Co. v. Mosele,

Quotes: []

Context: e in the county of residence, or convenient to potential witnesses by allowing for venue where the cause of action arose.” Baltimore & Ohio R.R. Co. v. Mosele, 67 Ill.2d 321, 328, 10 Ill.Dec. 602, 368 N.E.2d 88 (1977), citing E. Sunderland, Observations on t

Fictional by design: False; 

### First check: VERIFIED

Quoted sentence located in Mosele on CourtListener.

Excerpt read: 'The Illinois venue statute is designed to insure that the action will be brought either in a location convenient to the defendant, by providing for venue in the county of residence, or convenient to potential witnesses by allowing for venue where the cause of action arose.'

- https://www.courtlistener.com/opinion/2233472/baltimore-ohio-railroad-v-mosele/

### Second check: not required


## FNC-0269: E. Sunderland, Observations on the Illinois Civil Practice Act, 28 Ill. L. Rev. 861 (1934)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: other; as written: 28 Ill. L.Rev. 861; pincite: .

Cited for: Sunderland, Observations on the Illinois Civil Practice Act,

Quotes: []

Context: re & Ohio R.R. Co. v. Mosele, 67 Ill.2d 321, 328, 10 Ill.Dec. 602, 368 N.E.2d 88 (1977), citing E. Sunderland, Observations on the Illinois Civil Practice Act, 28 Ill. L.Rev. 861 (1934). Despite conceding that St. Clair County is a proper venue, defendants a

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The 1934 Sunderland article is cited in Langenhorst and other opinions, but the actual 28 Illinois Law Review 861 text was not accessible for direct reading. The journal citation is plausible; secondary quotations are insufficient for source verification.

Excerpt read: Langenhorst cites Edson R. Sunderland, Observations on the Illinois Civil Practice Act, 28 Ill. L. Rev. 861 (1934); article text not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf
- https://www.illinoiscourts.gov/files/99924.pdf/opinion

### Second check: not required


## FNC-0270: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217, 506 N.E.2d 1291 (1987)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: case; as written: 116 Ill.2d 217, 226; pincite: 226.

Cited for: A forum non conveniens motion “causes a court to look beyond the criterion of venue when it considers the relative convenience of a forum.” Bland v. Norfolk & Western Ry. Co.,

Quotes: []

Context: eniens motion “causes a court to look beyond the criterion of venue when it considers the relative convenience of a forum.” Bland v. Norfolk & Western Ry. Co., 116 Ill.2d 217, 226, 107 Ill.Dec. 236, 506 N.E.2d 1291 (1987). The fact that a defendant conducts b

Fictional by design: False; 

### First check: VERIFIED

Bland text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Bland, 116 Ill. 2d at 226: 'causes a court to look beyond the criterion of venue when it considers the relative convenience of a forum.'

- https://www.courtlistener.com/opinion/2210166/bland-v-norfolk-western-railway-co/

### Second check: not required


## FNC-0271: Vinson v. Allstate, 144 Ill. 2d 306, 579 N.E.2d 857 (1991)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: case; as written: 144 Ill.2d 306, 311; pincite: 311.

Cited for: The fact that a defendant conducts business within the county is not the only factor the court should consider in its analysis. Vinson v. Allstate,

Quotes: []

Context: 291 (1987). The fact that a defendant conducts business within the county is not the only factor the court should consider in its analysis. Vinson v. Allstate, 144 Ill.2d 306, 311, 162 Ill.Dec. 43, 579 N.E.2d 857 (1991). Forum non conveniens is an equitable d

Fictional by design: False; 

### First check: VERIFIED

Vinson passages read on CourtListener.

Excerpt read: 'a court ... may nevertheless decline jurisdiction of a case when it is apparent that trial in another forum ... would be more convenient and would better serve the ends of justice.'; 'the fact that Allstate conducts business within the county is not the only factor the court should consider in its analysis.'

- https://www.courtlistener.com/opinion/2238079/vinson-v-allstate/

### Second check: not required


## FNC-0272: Vinson v. Allstate, 144 Ill. 2d 306, 579 N.E.2d 857 (1991)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: case; as written: 144 Ill.2d at 310; pincite: 310.

Cited for: Forum non conveniens is an equitable doctrine founded in considerations of fundamental fairness and the sensible and effective administration of justice. Vinson,

Quotes: []

Context: rum non conveniens is an equitable doctrine founded in considerations of fundamental fairness and the sensible and effective administration of justice. Vinson, 144 Ill.2d at 310, 162 Ill.Dec. 43, 579 N.E.2d 857. This doctrine allows a trial court to decline

Fictional by design: False; 

### First check: VERIFIED

Vinson passages read on CourtListener.

Excerpt read: 'a court ... may nevertheless decline jurisdiction of a case when it is apparent that trial in another forum ... would be more convenient and would better serve the ends of justice.'; 'the fact that Allstate conducts business within the county is not the only factor the court should consider in its analysis.'

- https://www.courtlistener.com/opinion/2238079/vinson-v-allstate/

### Second check: not required


## FNC-0273: Vinson v. Allstate, 144 Ill. 2d 306, 579 N.E.2d 857 (1991)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: case; as written: 144 Ill.2d at 310; pincite: 310.

Cited for: This doctrine allows a trial court to decline jurisdiction when trial in another forum “would better serve the ends of justice.” Vinson,

Quotes: []

Context: c. 43, 579 N.E.2d 857. This doctrine allows a trial court to decline jurisdiction when trial in another forum “would better serve the ends of justice.” Vinson, 144 Ill.2d at 310, 162 Ill.Dec. 43, 579 N.E.2d 857. A trial court is afforded considerable discre

Fictional by design: False; 

### First check: VERIFIED

Vinson passages read on CourtListener.

Excerpt read: 'a court ... may nevertheless decline jurisdiction of a case when it is apparent that trial in another forum ... would be more convenient and would better serve the ends of justice.'; 'the fact that Allstate conducts business within the county is not the only factor the court should consider in its analysis.'

- https://www.courtlistener.com/opinion/2238079/vinson-v-allstate/

### Second check: not required


## FNC-0274: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: case; as written: 163 Ill.2d at 336; pincite: 336.

Cited for: A trial court is afforded considerable discretion in ruling on a forum non conveniens motion. Peile v. Skelgas, Inc.,

Quotes: []

Context: at 310, 162 Ill.Dec. 43, 579 N.E.2d 857. A trial court is afforded considerable discretion in ruling on a forum non conveniens motion. Peile v. Skelgas, Inc., 163 Ill.2d at 336, 206 Ill.Dec. 179, 645 N.E.2d 184; Dawdy, 207 Ill.2d at 176, 278 Ill.Dec. 92, 7

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Peile, 163 Ill. 2d at 336: 'The trial court is vested with considerable discretion in its determination of whether transfer is warranted'; 'If, however, the litigation has no practical connection to the forum ... the court should grant the motion for transfer.'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0275: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: case; as written: 207 Ill.2d at 176; pincite: 176.

Cited for: Skelgas, Inc., 163 Ill.2d at 336, 206 Ill.Dec. 179, 645 N.E.2d 184; Dawdy,

Quotes: []

Context: fforded considerable discretion in ruling on a forum non conveniens motion. Peile v. Skelgas, Inc., 163 Ill.2d at 336, 206 Ill.Dec. 179, 645 N.E.2d 184; Dawdy, 207 Ill.2d at 176, 278 Ill.Dec. 92, 797 N.E.2d 687 (“[t]he determination of a forum non convenien

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 176 (CourtListener 9819104): 'The determination of a forum non conveniens motion lies within the sound discretion of the trial court.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0276: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 5.

Authority type: case; as written: 207 Ill.2d at 176-77; pincite: 176-77.

Cited for: We will reverse the circuit court's decision only if defendants have shown that the circuit court abused its discretion in balancing the relevant factors. Dawdy,

Quotes: []

Context: will reverse the circuit court's decision only if defendants have shown that the circuit court abused its discretion in balancing the relevant factors. Dawdy, 207 Ill.2d at 176-77, 278 Ill.Dec. 92, 797 N.E.2d 687. A circuit court abuses its discretion in bala

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 176-77 (CourtListener 9819104): 'On review, the trial court's decision will be reversed only if it can be shown that the court abused its discretion in balancing the relevant factors.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0277: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 207 Ill.2d at 177; pincite: 177.

Cited for:  where no reasonable person would take the view adopted by the circuit court. Dawdy,

Quotes: []

Context: where no reasonable person would take the view adopted by the circuit court. Dawdy, 207 Ill.2d at 177, 278 Ill.Dec. 92, 797 N.E.2d 687. This court has repeatedly noted that the foru

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 177 (CourtListener 9819104): 'An abuse of discretion will be found where no reasonable person would take the view adopted by the trial court.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0278: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 198 Ill.2d at 520; pincite: 520.

Cited for: This court has repeatedly noted that the forum non conveniens doctrine gives courts discretionary power that should be exercised only in exceptional circumstances when the interests of justice require a trial in a more convenient forum. Guerine,

Quotes: []

Context: scretionary power that should be exercised only in exceptional circumstances when the interests of justice require a trial in a more convenient forum. Guerine, 198 Ill.2d at 520, 261 Ill.Dec. 763, 764 N.E.2d 54; Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 520 (CourtListener 3134965): ''discretionary power which should be exercised only in exceptional circumstances ...' In most instances, the plaintiffs initial choice of forum will prevail'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0279: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 163 Ill.2d at 335-36; pincite: 335-36.

Cited for: Guerine, 198 Ill.2d at 520, 261 Ill.Dec. 763, 764 N.E.2d 54; Peile,

Quotes: []

Context: nal circumstances when the interests of justice require a trial in a more convenient forum. Guerine, 198 Ill.2d at 520, 261 Ill.Dec. 763, 764 N.E.2d 54; Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179, 645 N.E.2d 184; Torres v. Walsh, 98 Ill.2d 338, 346, 74 Ill.

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Peile, 163 Ill. 2d at 335-36: 'The doctrine that was activated in Torres was designed to give the courts "discretionary power which should be exercised only in exceptional circumstances ..." In most instances, the plaintiffs initial choice of forum will prevail'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0280: Torres v. Walsh, 98 Ill. 2d 338, 456 N.E.2d 601 (1983)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 98 Ill.2d 338, 346; pincite: 346.

Cited for: Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179, 645 N.E.2d 184; Torres v. Walsh,

Quotes: []

Context: convenient forum. Guerine, 198 Ill.2d at 520, 261 Ill.Dec. 763, 764 N.E.2d 54; Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179, 645 N.E.2d 184; Torres v. Walsh, 98 Ill.2d 338, 346, 74 Ill.Dec. 880, 456 N.E.2d 601 (1983), citing Gulf Oil Corp. v. Gilbert, 330

Fictional by design: False; 

### First check: VERIFIED

Torres passages read on CourtListener (CourtListener lacks the 74 Ill. Dec. parallel, which is not a defect). Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Torres, 98 Ill. 2d at 346: 'the doctrine of forum non conveniens is a discretionary power which should be exercised only in exceptional circumstances when it has been shown that the interests of justice require a trial in a more convenient forum.'

- https://www.courtlistener.com/opinion/2103179/torres-v-walsh/

### Second check: not required


## FNC-0281: Gulf Oil Corp. v. Gilbert, 330 U.S. 501 (1947)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 330 U.S. 501; pincite: .

Cited for: 880, 456 N.E.2d 601 (1983), citing Gulf Oil Corp. v. Gilbert,

Quotes: []

Context: .2d at 335-36, 206 Ill.Dec. 179, 645 N.E.2d 184; Torres v. Walsh, 98 Ill.2d 338, 346, 74 Ill.Dec. 880, 456 N.E.2d 601 (1983), citing Gulf Oil Corp. v. Gilbert, 330 U.S. 501, 67 S.Ct. 839, 91 L.Ed. 1055 (1947). See also Dawdy, 207 Ill.2d at 176, 278 Ill

Fictional by design: False; 

### First check: VERIFIED

Gulf Oil passage read on CourtListener.

Excerpt read: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/104393/gulf-oil-corp-v-gilbert/

### Second check: not required


## FNC-0282: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 207 Ill.2d at 176; pincite: 176.

Cited for: Gilbert, 330 U.S. 501, 67 S.Ct. 839, 91 L.Ed. 1055 (1947). See also Dawdy,

Quotes: []

Context: 98 Ill.2d 338, 346, 74 Ill.Dec. 880, 456 N.E.2d 601 (1983), citing Gulf Oil Corp. v. Gilbert, 330 U.S. 501, 67 S.Ct. 839, 91 L.Ed. 1055 (1947). See also Dawdy, 207 Ill.2d at 176, 278 Ill.Dec. 92, 797 N.E.2d 687 (“ ‘[t]he test * * * is whether the relevant f

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 176 (CourtListener 9819104): 'The determination of a forum non conveniens motion lies within the sound discretion of the trial court.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0283: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 136 Ill.2d 101, 108; pincite: 108.

Cited for: 92, 797 N.E.2d 687 (“ ‘[t]he test * * * is whether the relevant factors, viewed in their totality, strongly favor transfer to the forum suggested by defendant’ ” (emphasis added)), quoting Griffith v. Mitsubishi Aircraft International, Inc.,

Quotes: []

Context: their totality, strongly favor transfer to the forum suggested by defendant’ ” (emphasis added)), quoting Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill.2d 101, 108, 143 Ill.Dec. 274, 554 N.E.2d 209 (1990). “The plaintiff has a substantial inte

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Griffith, 136 Ill. 2d at 108: 'The test, then, is whether the relevant factors, viewed in their totality, strongly favor transfer to the forum suggested by defendant.'

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0284: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 198 Ill.2d at 517; pincite: 517.

Cited for: “The plaintiff has a substantial interest in choosing the forum where his rights will be vindicated, and the plaintiff's forum choice should rarely be disturbed unless the other factors strongly favor transfer.” Guerine,

Quotes: []

Context: um where his rights will be vindicated, and the plaintiff's forum choice should rarely be disturbed unless the other factors strongly favor transfer.” Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54, citing Griffith, 136 Ill.2d at 106, 143 Ill.D

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 517 (CourtListener 3134965): 'Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly. ... The plaintiff has a substantial interest in choosing the forum where his rights will be vindicated'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0285: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 136 Ill.2d at 106; pincite: 106.

Cited for: al interest in choosing the forum where his rights will be vindicated, and the plaintiff's forum choice should rarely be disturbed unless the other factors strongly favor transfer.” Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54, citing Griffith,

Quotes: []

Context: ice should rarely be disturbed unless the other factors strongly favor transfer.” Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54, citing Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones v. Searle Laboratories, 93 Ill.2d 366,

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Griffith, 136 Ill. 2d at 106: 'A plaintiffs right to select the forum is a substantial one, and unless the factors weigh strongly in favor of transfer, "the plaintiffs choice of forum should rarely be disturbed."'

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0286: Jones v. Searle Laboratories, 93 Ill. 2d 366, 444 N.E.2d 157 (1982)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 93 Ill.2d 366, 372-73; pincite: 372-73.

Cited for: 763, 764 N.E.2d 54, citing Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones v. Searle Laboratories,

Quotes: []

Context: uerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54, citing Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones v. Searle Laboratories, 93 Ill.2d 366, 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157 (1982); Gulf Oil, 330 U.S. at 508-09, 67 S.Ct.

Fictional by design: False; 

### First check: VERIFIED

Jones passage read on CourtListener.

Excerpt read: Jones quotes Gulf Oil: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/2032797/jones-v-searle-laboratories/

### Second check: not required


## FNC-0287: Gulf Oil Corp. v. Gilbert, 330 U.S. 501 (1947)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 330 U.S. at 508-09; pincite: 508-09.

Cited for: Searle Laboratories, 93 Ill.2d 366, 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157 (1982); Gulf Oil,

Quotes: []

Context: th, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones v. Searle Laboratories, 93 Ill.2d 366, 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157 (1982); Gulf Oil, 330 U.S. at 508-09, 67 S.Ct. at 843, 91 L.Ed. at 1062-63; Restatement (Second) of Conflict of Laws

Fictional by design: False; 

### First check: VERIFIED

Gulf Oil passage read on CourtListener.

Excerpt read: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/104393/gulf-oil-corp-v-gilbert/

### Second check: not required


## FNC-0288: Restatement (Second) of Conflict of Laws § 84 cmt. c (1971)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: restatement_or_treatise; as written: Restatement (Second) of Conflict of Laws § 84, Comment c; pincite: .

Cited for: Gulf Oil, 330 U.S. at 508-09, 67 S.Ct. at 843, 91 L.Ed. at 1062-63;

Quotes: []

Context: ones v. Searle Laboratories, 93 Ill.2d 366, 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157 (1982); Gulf Oil, 330 U.S. at 508-09, 67 S.Ct. at 843, 91 L.Ed. at 1062-63; Restatement (Second) of Conflict of Laws § 84, Comment c (1971) (“since it is for the plaintiff to choose the place of suit, his choice

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The attached opinion reproduces the asserted Restatement language, and another court opinion independently quotes part of comment c, but I did not obtain the ALI Restatement (Second) of Conflict of Laws §84 comment c itself. A quotation in a judicial opinion corroborates the wording but does not satisfy this audit’s direct-source reading requirement.

Excerpt read: The judicial reproductions say plaintiff choice should not be disturbed except for weighty reasons and dismissal requires a suitable alternative forum; ALI source text not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf
- https://www.ali.org/publications/restatement-law-second/conflict-laws
- https://cases.justia.com/montana/supreme-court/2015-da-14-0465.pdf

### Second check: not required


## FNC-0289: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 198 Ill.2d at 517; pincite: 517.

Cited for: However, the plaintiff's interest in choosing the forum receives “somewhat less deference when neither the plaintiff's residence nor the site of the accident or injury is located in the chosen forum.” Guerine,

Quotes: []

Context: forum receives “somewhat less deference when neither the plaintiff's residence nor the site of the accident or injury is located in the chosen forum.” Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54. “ ‘In most instances, the plaintiff's initial

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 517 (CourtListener 3134965): 'Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly. ... The plaintiff has a substantial interest in choosing the forum where his rights will be vindicated'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0290: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 198 Ill.2d at 520; pincite: 520.

Cited for: s, the plaintiff's initial choice of forum will prevail, provided venue is proper and the inconvenience factors attached to such forum do not greatly outweigh the plaintiff's substantial right to try the case in the chosen forum.’ ” (Emphasis added.) Guerine,

Quotes: []

Context: nce factors attached to such forum do not greatly outweigh the plaintiff's substantial right to try the case in the chosen forum.’ ” (Emphasis added.) Guerine, 198 Ill.2d at 520, 261 Ill.Dec. 763, 764 N.E.2d 54, quoting Peile, 163 Ill.2d at 335-36, 206 Ill.

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 520 (CourtListener 3134965): ''discretionary power which should be exercised only in exceptional circumstances ...' In most instances, the plaintiffs initial choice of forum will prevail'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0291: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 163 Ill.2d at 335-36; pincite: 335-36.

Cited for: enue is proper and the inconvenience factors attached to such forum do not greatly outweigh the plaintiff's substantial right to try the case in the chosen forum.’ ” (Emphasis added.) Guerine, 198 Ill.2d at 520, 261 Ill.Dec. 763, 764 N.E.2d 54, quoting Peile,

Quotes: []

Context: ntiff's substantial right to try the case in the chosen forum.’ ” (Emphasis added.) Guerine, 198 Ill.2d at 520, 261 Ill.Dec. 763, 764 N.E.2d 54, quoting Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179, 645 N.E.2d 184. Although this is a difficult standard for de

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Peile, 163 Ill. 2d at 335-36: 'The doctrine that was activated in Torres was designed to give the courts "discretionary power which should be exercised only in exceptional circumstances ..." In most instances, the plaintiffs initial choice of forum will prevail'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0292: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 198 Ill.2d at 521; pincite: 521.

Cited for: Although this is a difficult standard for defendants to meet, “it does not foreclose legitimate transfers when the balance of factors strongly favors litigation in another forum.” (Emphases added.) Guerine,

Quotes: []

Context: dants to meet, “it does not foreclose legitimate transfers when the balance of factors strongly favors litigation in another forum.” (Emphases added.) Guerine, 198 Ill.2d at 521, 261 Ill.Dec. 763, 764 N.E.2d 54. In deciding a forum non conveniens motion, a

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 521 (CourtListener 3134965): 'the battle over forum begins with the plaintiffs choice already in the lead. ... it does not foreclose legitimate transfers when the balance of factors strongly favors litigation in another forum.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0293: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 207 Ill.2d at 175-76; pincite: 175-76.

Cited for: In deciding a forum non conveniens motion, a court must consider all of the relevant factors, without emphasizing any one factor . Dawdy,

Quotes: []

Context: . 763, 764 N.E.2d 54. In deciding a forum non conveniens motion, a court must consider all of the relevant factors, without emphasizing any one factor . Dawdy, 207 Ill.2d at 175-76, 278 Ill.Dec. 92, 797 N.E.2d 687 (collecting cases). Each forum non conveniens

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 175-76 (CourtListener 9819104): 'If central emphasis were placed on any one factor, the forum non conveniens doctrine would lose much of the very flexibility that makes it so valuable.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0294: Satkowiak v. Chesapeake & Ohio Ry. Co., 106 Ill. 2d 224, 478 N.E.2d 370 (1985)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 106 Ill.2d 224, 228; pincite: 228.

Cited for: Each forum non conveniens case must be considered as unique on its facts. Satkowiak v. Chesapeake & Ohio Ry. Co.,

Quotes: []

Context: l.Dec. 92, 797 N.E.2d 687 (collecting cases). Each forum non conveniens case must be considered as unique on its facts. Satkowiak v. Chesapeake & Ohio Ry. Co., 106 Ill.2d 224, 228, 88 Ill.Dec. 55, 478 N.E.2d 370 (1985); see Moore v. Chicago & North Western Tr

Fictional by design: False; 

### First check: VERIFIED

Sentence located in Satkowiak on CourtListener.

Excerpt read: 'Each case must be considered as unique on its facts.'

- https://www.courtlistener.com/opinion/2248572/satkowiak-v-chesapeake-ohio-railway-co/

### Second check: not required


## FNC-0295: Moore v. Chicago & North Western Transportation Co., 99 Ill. 2d 73, 457 N.E.2d 417 (1983)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 99 Ill.2d 73, 83; pincite: 83.

Cited for: 55, 478 N.E.2d 370 (1985); see Moore v. Chicago & North Western Transportation Co.,

Quotes: []

Context: s. Satkowiak v. Chesapeake & Ohio Ry. Co., 106 Ill.2d 224, 228, 88 Ill.Dec. 55, 478 N.E.2d 370 (1985); see Moore v. Chicago & North Western Transportation Co., 99 Ill.2d 73, 83, 75 Ill.Dec. 423, 457 N.E.2d 417 (1983) ( “all factors essential to the trial o

Fictional by design: False; 

### First check: VERIFIED

Moore read in full on CourtListener.

Excerpt read: 'As previously noted, all factors essential to the trial of a particular case must be balanced in determining whether to dismiss an action on forum non conveniens grounds.'

- https://www.courtlistener.com/opinion/2076615/moore-v-chicago-north-western-transportation-co/

### Second check: not required


## FNC-0296: Darnell v. Ralph Korte Equipment Co., 144 Ill. App. 3d 564, 494 N.E.2d 1206 (1986)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 144 Ill.App.3d 564, 566; pincite: 566.

Cited for: 423, 457 N.E.2d 417 (1983) ( “all factors essential to the trial of a particular case must be balanced in determining whether to dismiss an action on forum non conveniens grounds”); Darnell v. Ralph Korte Equipment Co.,

Quotes: []

Context: rial of a particular case must be balanced in determining whether to dismiss an action on forum non conveniens grounds”); Darnell v. Ralph Korte Equipment Co., 144 Ill.App.3d 564, 566, 98 Ill.Dec. 879, 494 N.E.2d 1206 (1986). In Guerine, 198 Ill.2d 511, 261 Ill.D

Fictional by design: False; 

### First check: VERIFIED

Sentence located in Darnell on CourtListener.

Excerpt read: 'Each case must be considered as unique on its facts. (Satkowiak ...)'

- https://www.courtlistener.com/opinion/2033300/darnell-v-ralph-korte-equipment-co/

### Second check: not required


## FNC-0297: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 198 Ill.2d 511; pincite: .

Cited for: Ralph Korte Equipment Co., 144 Ill.App.3d 564, 566, 98 Ill.Dec. 879, 494 N.E.2d 1206 (1986). In Guerine,

Quotes: []

Context: n action on forum non conveniens grounds”); Darnell v. Ralph Korte Equipment Co., 144 Ill.App.3d 564, 566, 98 Ill.Dec. 879, 494 N.E.2d 1206 (1986). In Guerine, 198 Ill.2d 511, 261 Ill.Dec. 763, 764 N.E.2d 54, we restated the private and public interest f

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Ill. Reports text (CourtListener 3134965): 'First American Bank, as executor of Angel's estate ...'; N.E.2d text (2056494) caption 'FIRST NATIONAL BANK et al., Appellants, v. Richard GUERINE et al.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0298: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 6.

Authority type: case; as written: 198 Ill.2d at 516; pincite: 516.

Cited for: and (3) all other practical problems that make trial of a case easy, expeditious, and inexpensive * * *.” Guerine,

Quotes: []

Context: testimonial, documentary, and real evidence; and (3) all other practical problems that make trial of a case easy, expeditious, and inexpensive * * *.” Guerine, 198 Ill.2d at 516, 261 Ill.Dec. 763, 764 N.E.2d 54. Public interest factors include (1) the inter

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 516 (CourtListener 3134965): 'In Illinois, the private interest factors include (1) the convenience of the parties; (2) the relative ease of access to sources of testimonial, documentary, and real evidence; and (3) all other practical problems'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0299: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 7.

Authority type: case; as written: 198 Ill.2d at 516-17; pincite: 516-17.

Cited for: and (3) the administrative difficulties presented by adding litigation to already congested court dockets. Guerine,

Quotes: []

Context: litigation; and (3) the administrative difficulties presented by adding litigation to already congested court dockets. Guerine, 198 Ill.2d at 516-17, 261 Ill.Dec. 763, 764 N.E.2d 54. These factors are relevant considerations for

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 516-17 (CourtListener 3134965): 'The public interest factors include (1) the interest in deciding localized controversies locally; (2) the unfairness of imposing the expense of a trial and the burden of jury duty ...; and (3) the administrative difficulties'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0300: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 7.

Authority type: case; as written: 198 Ill.2d at 517; pincite: 517.

Cited for: These factors are relevant considerations for both interstate and intrastate forum non conveniens analysis. Guerine,

Quotes: []

Context: t 516-17, 261 Ill.Dec. 763, 764 N.E.2d 54. These factors are relevant considerations for both interstate and intrastate forum non conveniens analysis. Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54. The burden is on the defendant to show that r

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 517 (CourtListener 3134965): 'Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly. ... The plaintiff has a substantial interest in choosing the forum where his rights will be vindicated'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0301: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 7.

Authority type: case; as written: 136 Ill.2d at 107; pincite: 107.

Cited for: The burden is on the defendant to show that relevant private and public interest factors “strongly favor” the defendant's choice of forum to warrant disturbing plaintiff's choice. Griffith,

Quotes: []

Context: to show that relevant private and public interest factors “strongly favor” the defendant's choice of forum to warrant disturbing plaintiff's choice. Griffith, 136 Ill.2d at 107, 143 Ill.Dec. 274, 554 N.E.2d 209. The private interest factors are not weighed

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Griffith, 136 Ill. 2d at 107: defendants' proposed 'equal balancing test' rejected; the unequal test requires that the factors 'strongly favor' transfer.

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0302: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 7.

Authority type: case; as written: 198 Ill.2d at 518; pincite: 518.

Cited for: rather, the trial court must evaluate the total circumstances of the case in determining whether the defendant has proven that the balance of factors strongly favors transfer. Guerine,

Quotes: []

Context: ust evaluate the total circumstances of the case in determining whether the defendant has proven that the balance of factors strongly favors transfer. Guerine, 198 Ill.2d at 518, 261 Ill.Dec. 763, 764 N.E.2d 54. The defendant must show that the plaintiff's

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 518 (CourtListener 3134965): 'the trial court must evaluate the total circumstances of the case in deciding whether the defendant has proven that the balance of factors strongly favors transfer. ... The defendant cannot assert that the plaintiffs chosen forum is inconvenient to the plaintiff.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0303: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 7.

Authority type: case; as written: 198 Ill.2d at 518; pincite: 518.

Cited for: The defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties. Guerine,

Quotes: []

Context: . The defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties. Guerine, 198 Ill.2d at 518, 261 Ill.Dec. 763, 764 N.E.2d 54. However, the defendant cannot assert that the

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 518 (CourtListener 3134965): 'the trial court must evaluate the total circumstances of the case in deciding whether the defendant has proven that the balance of factors strongly favors transfer. ... The defendant cannot assert that the plaintiffs chosen forum is inconvenient to the plaintiff.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0304: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 7.

Authority type: case; as written: 198 Ill.2d at 518; pincite: 518.

Cited for: However, the defendant cannot assert that the plaintiff's chosen forum is inconvenient to the plaintiff. Guerine,

Quotes: []

Context: l.2d at 518, 261 Ill.Dec. 763, 764 N.E.2d 54. However, the defendant cannot assert that the plaintiff's chosen forum is inconvenient to the plaintiff. Guerine, 198 Ill.2d at 518, 261 Ill.Dec. 763, 764 N.E.2d 54. Unless the balance of factors strongly favor

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 518 (CourtListener 3134965): 'the trial court must evaluate the total circumstances of the case in deciding whether the defendant has proven that the balance of factors strongly favors transfer. ... The defendant cannot assert that the plaintiffs chosen forum is inconvenient to the plaintiff.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0305: Gulf Oil Corp. v. Gilbert, 330 U.S. 501 (1947)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 7.

Authority type: case; as written: 330 U.S. at 507-08; pincite: 507-08.

Cited for: Unless the balance of factors strongly favor a defendant's choice of forum, the plaintiff's choice of forum should rarely be disturbed. Gulf Oil,

Quotes: []

Context: 64 N.E.2d 54. Unless the balance of factors strongly favor a defendant's choice of forum, the plaintiff's choice of forum should rarely be disturbed. Gulf Oil, 330 U.S. at 507-08, 67 S.Ct. at 842-43, 91 L.Ed. at 1062. In Guerine, a Kane County resident was k

Fictional by design: False; 

### First check: VERIFIED

Gulf Oil passage read on CourtListener.

Excerpt read: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/104393/gulf-oil-corp-v-gilbert/

### Second check: not required


## FNC-0306: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 7.

Authority type: case; as written: 198 Ill.2d at 514; pincite: 514.

Cited for: We evaluated the continued vitality of the intrastate forum non conveniens doctrine in Guerine and reaffirmed the doctrine as Illinois law. Guerine,

Quotes: []

Context: necessary. We evaluated the continued vitality of the intrastate forum non conveniens doctrine in Guerine and reaffirmed the doctrine as Illinois law. Guerine, 198 Ill.2d at 514, 261 Ill.Dec. 763, 764 N.E.2d 54. In determining that the trial court abused it

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 514 (CourtListener 3134965): 'We reaffirm that the doctrine is Illinois law, but we conclude that the trial court abused its discretion in granting J.Q. Tex's motion to transfer venue.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0307: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 7.

Authority type: case; as written: 198 Ill.2d at 525-26; pincite: 525-26.

Cited for: otion to transfer venue from Cook County to De Kalb County, we noted that both Cook County and De Kalb County had significant ties to the case and that potential witnesses were scattered among several counties, including the plaintiff's chosen forum. Guerine,

Quotes: []

Context: lb County had significant ties to the case and that potential witnesses were scattered among several counties, including the plaintiff's chosen forum. Guerine, 198 Ill.2d at 525-26, 261 Ill.Dec. 763, 764 N.E.2d 54. This court again had the opportunity to revie

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Langenhorst describes Guerine's trial court as transferring 'from Cook County to De Kalb County'; per Guerine (attachment pp.1-2, 8) the motion sought De Kalb but the court let plaintiffs choose and the case was transferred to Kane County. The cited holding (abuse of discretion; scattered witnesses; ties to Cook and De Kalb) is accurate.

Excerpt read: Supplied Guerine opinion PDF p.8: 'we reverse the decision of the trial court transferring this cause to Kane County'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0308: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 7.

Authority type: case; as written: 207 Ill.2d 167; pincite: .

Cited for: This court again had the opportunity to review the doctrine of intrastate forum non conveniens in Dawdy,

Quotes: []

Context: 198 Ill.2d at 525-26, 261 Ill.Dec. 763, 764 N.E.2d 54. This court again had the opportunity to review the doctrine of intrastate forum non conveniens in Dawdy, 207 Ill.2d 167, 278 Ill.Dec. 92, 797 N.E.2d 687. In Dawdy, the plaintiff, a Green County resid

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Accurate summary of Dawdy, except that Langenhorst calls the Dawdy plaintiff 'a Green County resident'; Dawdy says Greene County (the official Langenhorst text has the same slip).

Excerpt read: Dawdy (CourtListener 9819104): 'Plaintiff resides in Greene County. The action arose in Macoupin County.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0309: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 7.

Authority type: case; as written: 207 Ill.2d at 177; pincite: 177.

Cited for: In applying the forum non conveniens factors, the Dawdy majority concluded that the circuit court abused its discretion in denying defendants' motion to transfer the cause to Macoupin County. Dawdy,

Quotes: []

Context: ctors, the Dawdy majority concluded that the circuit court abused its discretion in denying defendants' motion to transfer the cause to Macoupin County. Dawdy, 207 Ill.2d at 177, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court first examined the private in

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 177 (CourtListener 9819104): 'An abuse of discretion will be found where no reasonable person would take the view adopted by the trial court.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0310: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 178; pincite: 178.

Cited for: 

Quotes: []

Context: 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. The court also recognized that the possibilit

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 178 (CourtListener 9819104): 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County. ... This convenience factor is not concerned with the necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0311: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 179; pincite: 179.

Cited for: The court also recognized that the possibility of having a jury view the scene of the accident could be accomplished more expeditiously if the case were tried in Macoupin County. Dawdy,

Quotes: []

Context: that the possibility of having a jury view the scene of the accident could be accomplished more expeditiously if the case were tried in Macoupin County. Dawdy, 207 Ill.2d at 179, 278 Ill.Dec. 92, 797 N.E.2d 687. The fact that the plaintiff's attorneys maint

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 179 (CourtListener 9819104): 'the necessity or propriety of viewing the scene is a decision left within the discretion of the trial court. ... While a court may consider this factor, "little weight should be accorded it."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0312: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 179; pincite: 179.

Cited for: The fact that the plaintiff's attorneys maintained an office in Madison County and defendants' attorneys were located a short distance away in St. Clair County was accorded little weight. Dawdy,

Quotes: []

Context: neys maintained an office in Madison County and defendants' attorneys were located a short distance away in St. Clair County was accorded little weight. Dawdy, 207 Ill.2d at 179, 278 Ill.Dec. 92, 797 N.E.2d 687. The court rejected plaintiff's contention tha

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 179 (CourtListener 9819104): 'the necessity or propriety of viewing the scene is a decision left within the discretion of the trial court. ... While a court may consider this factor, "little weight should be accorded it."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0313: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 180; pincite: 180.

Cited for: The court rejected plaintiff's contention that trial in an adjacent county was conclusively not inconvenient for a defendant and emphasized that “no single forum non conveniens factor should be accorded central emphasis or conclusive effect.” Dawdy,

Quotes: []

Context: y not inconvenient for a defendant and emphasized that “no single forum non conveniens factor should be accorded central emphasis or conclusive effect.” Dawdy, 207 Ill.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687, citing Jones, 93 Ill.2d at 373, 67 Ill.Dec. 1

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 180 (CourtListener 9819104): 'We cannot accept the contention that trial in an adjacent county is conclusively not inconvenient for a defendant. ... no single forum non conveniens factor should be accorded central emphasis or conclusive effect.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0314: Jones v. Searle Laboratories, 93 Ill. 2d 366, 444 N.E.2d 157 (1982)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 93 Ill.2d at 373; pincite: 373.

Cited for: an adjacent county was conclusively not inconvenient for a defendant and emphasized that “no single forum non conveniens factor should be accorded central emphasis or conclusive effect.” Dawdy, 207 Ill.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687, citing Jones,

Quotes: []

Context: forum non conveniens factor should be accorded central emphasis or conclusive effect.” Dawdy, 207 Ill.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687, citing Jones, 93 Ill.2d at 373, 67 Ill.Dec. 118, 444 N.E.2d 157. The Dawdy court concluded that, on a whole, t

Fictional by design: False; 

### First check: VERIFIED

Jones passage read on CourtListener.

Excerpt read: Jones quotes Gulf Oil: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/2032797/jones-v-searle-laboratories/

### Second check: not required


## FNC-0315: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 180; pincite: 180.

Cited for: The Dawdy court concluded that, on a whole, the private interest factors favored the convenience of Macoupin County over Madison County. Dawdy,

Quotes: []

Context: 444 N.E.2d 157. The Dawdy court concluded that, on a whole, the private interest factors favored the convenience of Macoupin County over Madison County. Dawdy, 207 Ill.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court then determined that the publ

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 180 (CourtListener 9819104): 'We cannot accept the contention that trial in an adjacent county is conclusively not inconvenient for a defendant. ... no single forum non conveniens factor should be accorded central emphasis or conclusive effect.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0316: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 180-81; pincite: 180-81.

Cited for: The Dawdy court then determined that the public interest factors strongly weighed against Madison County. Dawdy,

Quotes: []

Context: ll.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court then determined that the public interest factors strongly weighed against Madison County. Dawdy, 207 Ill.2d at 180-81, 278 Ill.Dec. 92, 797 N.E.2d 687. Although the court recognized that court cong

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 180-81 (CourtListener 9819104): 'The public interest factors strongly weigh against Madison County as the appropriate forum in which this case should be tried.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0317: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 181; pincite: 181.

Cited for: Although the court recognized that court congestion was relatively insignificant, the crowded docket of Madison County was “ ‘of great concern.’ ” Dawdy,

Quotes: []

Context: 687. Although the court recognized that court congestion was relatively insignificant, the crowded docket of Madison County was “ ‘of great concern.’ ” Dawdy, 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687, quoting Bland, 116 Ill.2d at 230, 107 Ill.Dec

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 181 (CourtListener 9819104): 'The court congestion factor, by itself, is relatively insignificant ... there were 1,867 jury actions for damages in excess of $50,000 pending in Madison County, while only 137 ... "crowded to the point where congestion is of great concern."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0318: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217, 506 N.E.2d 1291 (1987)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 116 Ill.2d at 230; pincite: 230.

Cited for: Although the court recognized that court congestion was relatively insignificant, the crowded docket of Madison County was “ ‘of great concern.’ ” Dawdy, 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687, quoting Bland,

Quotes: []

Context: ively insignificant, the crowded docket of Madison County was “ ‘of great concern.’ ” Dawdy, 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687, quoting Bland, 116 Ill.2d at 230, 107 Ill.Dec. 236, 506 N.E.2d 1291. Moreover, the fact that the accident occurr

Fictional by design: False; 

### First check: VERIFIED

Bland text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Bland, 116 Ill. 2d at 230: 'the docket of the circuit court of Madison County is still crowded to the point where congestion is of great concern.'

- https://www.courtlistener.com/opinion/2210166/bland-v-norfolk-western-railway-co/

### Second check: not required


## FNC-0319: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 183; pincite: 183.

Cited for: Moreover, the fact that the accident occurred in Macoupin County gave that county a local interest in the action. Dawdy,

Quotes: []

Context: 30, 107 Ill.Dec. 236, 506 N.E.2d 1291. Moreover, the fact that the accident occurred in Macoupin County gave that county a local interest in the action. Dawdy, 207 Ill.2d at 183, 278 Ill.Dec. 92, 797 N.E.2d 687. The court further concluded that the resident

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 183 (CourtListener 9819104): 'Clearly, Madison County has little or no interest in trying the action of a nonresident whose claim arose in Macoupin County. ... Most significantly, the fact that the accident occurred in Macoupin County gives the action a local interest.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0320: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 183; pincite: 183.

Cited for: The court further concluded that the residents of Madison County should not be burdened with jury duty because the action did not arise in and had no relation to Madison County. Dawdy,

Quotes: []

Context: ed that the residents of Madison County should not be burdened with jury duty because the action did not arise in and had no relation to Madison County. Dawdy, 207 Ill.2d at 183, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court distinguished Guerine on the

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 183 (CourtListener 9819104): 'Clearly, Madison County has little or no interest in trying the action of a nonresident whose claim arose in Macoupin County. ... Most significantly, the fact that the accident occurred in Macoupin County gives the action a local interest.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0321: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 184; pincite: 184.

Cited for: The Dawdy court distinguished Guerine on the basis that, in Dawdy, none of the witnesses resided in the plaintiff's chosen forum. Dawdy,

Quotes: []

Context: c. 92, 797 N.E.2d 687. The Dawdy court distinguished Guerine on the basis that, in Dawdy, none of the witnesses resided in the plaintiff's chosen forum. Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687. The court acknowledged that deference to plai

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 184 (CourtListener 9819104): 'In this case, however, none of the witnesses reside in Madison County and Macoupin County has a predominant connection to this case. ... the balance of factors strongly favors transfer to Macoupin County.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0322: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 184; pincite: 184.

Cited for: The court acknowledged that deference to plaintiff's choice of Madison County was reduced because he did not reside there and the action did not arise there. Dawdy,

Quotes: []

Context: ourt acknowledged that deference to plaintiff's choice of Madison County was reduced because he did not reside there and the action did not arise there. Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687. Accordingly, the court held that the circuit

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 184 (CourtListener 9819104): 'In this case, however, none of the witnesses reside in Madison County and Macoupin County has a predominant connection to this case. ... the balance of factors strongly favors transfer to Macoupin County.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0323: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 8.

Authority type: case; as written: 207 Ill.2d at 185; pincite: 185.

Cited for: Accordingly, the court held that the circuit court of Madison County abused its discretion in denying defendants' motion to transfer venue to Macoupin County based on the doctrine of intrastate forum non conveniens. Dawdy,

Quotes: []

Context: ounty abused its discretion in denying defendants' motion to transfer venue to Macoupin County based on the doctrine of intrastate forum non conveniens. Dawdy, 207 Ill.2d at 185, 278 Ill.Dec. 92, 797 N.E.2d 687. We now examine the current case under our exi

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 185 (CourtListener 9819104): 'we hold that the circuit court abused its discretion in denying defendants' motion to transfer venue from Madison County to Macoupin County'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0324: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 9.

Authority type: case; as written: 207 Ill.2d at 182; pincite: 182.

Cited for: First, we recognize that “[i]t is assumed on a forum non conveniens motion that the plaintiff's chosen forum is a proper venue for the action.” Dawdy,

Quotes: []

Context: County. First, we recognize that “[i]t is assumed on a forum non conveniens motion that the plaintiff's chosen forum is a proper venue for the action.” Dawdy, 207 Ill.2d at 182, 278 Ill.Dec. 92, 797 N.E.2d 687. Plaintiff's choice of forum is entitled to su

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 182 (CourtListener 9819104): 'It is assumed on a forum non conveniens motion that the plaintiffs chosen forum is a proper venue for the action. ... the fact that the defendant conducts business within Madison County is not a dispositive factor in this case.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0325: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 9.

Authority type: case; as written: 198 Ill.2d at 521; pincite: 521.

Cited for: Plaintiff's choice of forum is entitled to substantial deference. Guerine,

Quotes: []

Context: er venue for the action.” Dawdy, 207 Ill.2d at 182, 278 Ill.Dec. 92, 797 N.E.2d 687. Plaintiff's choice of forum is entitled to substantial deference. Guerine, 198 Ill.2d at 521, 261 Ill.Dec. 763, 764 N.E.2d 54 (“the battle over forum begins with the plaint

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 521 (CourtListener 3134965): 'the battle over forum begins with the plaintiffs choice already in the lead. ... it does not foreclose legitimate transfers when the balance of factors strongly favors litigation in another forum.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0326: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 9.

Authority type: case; as written: 198 Ill.2d at 517; pincite: 517.

Cited for: Clair County is entitled to somewhat less deference. Guerine,

Quotes: []

Context: nor the site of the accident is located in St. Clair County and, thus, plaintiff's choice of St. Clair County is entitled to somewhat less deference. Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54; Dawdy, 207 Ill.2d at 173-74, 278 Ill.Dec. 92,

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 517 (CourtListener 3134965): 'Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly. ... The plaintiff has a substantial interest in choosing the forum where his rights will be vindicated'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0327: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 9.

Authority type: case; as written: 207 Ill.2d at 173-74; pincite: 173-74.

Cited for: Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54; Dawdy,

Quotes: []

Context: y and, thus, plaintiff's choice of St. Clair County is entitled to somewhat less deference. Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54; Dawdy, 207 Ill.2d at 173-74, 278 Ill.Dec. 92, 797 N.E.2d 687. “ ‘[W]hile the deference to be accorded to a

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 173-74 (CourtListener 9819104): 'When the plaintiff is foreign, however, this assumption is much less reasonable. ... a foreign plaintiffs choice deserves less deference.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0328: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 9.

Authority type: case; as written: 198 Ill.2d at 518; pincite: 518.

Cited for: e deference to be accorded to a plaintiff regarding his choice of forum is less when the plaintiff chooses a forum other than where he resides * * * nonetheless the deference to be accorded is only less, as opposed to none.’ ” (Emphases in original.) Guerine,

Quotes: []

Context: hooses a forum other than where he resides * * * nonetheless the deference to be accorded is only less, as opposed to none.’ ” (Emphases in original.) Guerine, 198 Ill.2d at 518, 261 Ill.Dec. 763, 764 N.E.2d 54, quoting Elling v. State Farm Mutual Automobil

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 518 (CourtListener 3134965): 'the trial court must evaluate the total circumstances of the case in deciding whether the defendant has proven that the balance of factors strongly favors transfer. ... The defendant cannot assert that the plaintiffs chosen forum is inconvenient to the plaintiff.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0329: Elling v. State Farm Mutual Automobile Insurance Co., 291 Ill. App. 3d 311, 683 N.E.2d 929 (1997)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 9.

Authority type: case; as written: 291 Ill.App.3d 311, 318; pincite: 318.

Cited for: 763, 764 N.E.2d 54, quoting Elling v. State Farm Mutual Automobile Insurance Co.,

Quotes: []

Context: to none.’ ” (Emphases in original.) Guerine, 198 Ill.2d at 518, 261 Ill.Dec. 763, 764 N.E.2d 54, quoting Elling v. State Farm Mutual Automobile Insurance Co., 291 Ill.App.3d 311, 318, 225 Ill.Dec. 426, 683 N.E.2d 929 (1997). Defendants assert that trial in Clint

Fictional by design: False; 

### First check: VERIFIED

Quoted language located in Elling (the ellipsis omits 'or where the injury occurred').

Excerpt read: 'while the deference to be accorded to a plaintiff regarding his choice of forum is less when the plaintiff chooses a forum other than where he resides or where the injury occurred, nonetheless the deference to be accorded is only less, as opposed to none'

- https://www.courtlistener.com/opinion/2052172/elling-v-state-farm-mutual-automobile-insurance/

### Second check: not required


## FNC-0330: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 9.

Authority type: case; as written: 198 Ill.2d at 518; pincite: 518.

Cited for: However, “defendants cannot assert that the plaintiff's chosen forum is inconvenient to the plaintiff.” Guerine,

Quotes: []

Context: nty would be more convenient to the plaintiff. However, “defendants cannot assert that the plaintiff's chosen forum is inconvenient to the plaintiff.” Guerine, 198 Ill.2d at 518, 261 Ill.Dec. 763, 764 N.E.2d 54. In weighing the private interest factors, we

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 518 (CourtListener 3134965): 'the trial court must evaluate the total circumstances of the case in deciding whether the defendant has proven that the balance of factors strongly favors transfer. ... The defendant cannot assert that the plaintiffs chosen forum is inconvenient to the plaintiff.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0331: Boner v. Peabody Coal Co., 142 Ill. 2d 523, 568 N.E.2d 883 (1991)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 10.

Authority type: case; as written: 142 Ill.2d 523, 534; pincite: 534.

Cited for: We acknowledge, however, that the location of the parties' attorneys is accorded little weight in determining a forum non conveniens motion. Boner v. Peabody Coal Co.,

Quotes: []

Context: wledge, however, that the location of the parties' attorneys is accorded little weight in determining a forum non conveniens motion. Boner v. Peabody Coal Co., 142 Ill.2d 523, 534, 154 Ill.Dec. 662, 568 N.E.2d 883 (1991). Not only have defendants not claimed

Fictional by design: False; 

### First check: VERIFIED

Boner text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Boner, 142 Ill. 2d at 534: 'While a circuit court may consider this factor, little weight should be accorded it.'

- https://www.courtlistener.com/opinion/2094308/boner-v-peabody-coal-co/

### Second check: not required


## FNC-0332: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 10.

Authority type: case; as written: 198 Ill.2d at 518; pincite: 518.

Cited for: We reiterate that the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties. Guerine,

Quotes: []

Context: t the defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties. Guerine, 198 Ill.2d at 518, 261 Ill.Dec. 763, 764 N.E.2d 54. We discern no inconvenience for the defendant

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 518 (CourtListener 3134965): 'the trial court must evaluate the total circumstances of the case in deciding whether the defendant has proven that the balance of factors strongly favors transfer. ... The defendant cannot assert that the plaintiffs chosen forum is inconvenient to the plaintiff.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0333: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 10.

Authority type: case; as written: 198 Ill.2d at 519-20; pincite: 519-20.

Cited for: When adjoining counties are involved, “ ‘ “[t]he battle over the forum results in a battle over the minutiae.” ’ ” Guerine,

Quotes: []

Context: witnesses are minimally different. When adjoining counties are involved, “ ‘ “[t]he battle over the forum results in a battle over the minutiae.” ’ ” Guerine, 198 Ill.2d at 519-20, 261 Ill.Dec. 763, 764 N.E.2d 54, quoting Peile, 163 Ill.2d at 335, 206 Ill.Dec

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 519-20 (CourtListener 3134965): 'even agreeing with a concurring justice in the appellate court that "'[t]he battle over the forum results in a battle over minutiae.'"'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0334: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 10.

Authority type: case; as written: 163 Ill.2d at 335; pincite: 335.

Cited for: When adjoining counties are involved, “ ‘ “[t]he battle over the forum results in a battle over the minutiae.” ’ ” Guerine, 198 Ill.2d at 519-20, 261 Ill.Dec. 763, 764 N.E.2d 54, quoting Peile,

Quotes: []

Context: ed, “ ‘ “[t]he battle over the forum results in a battle over the minutiae.” ’ ” Guerine, 198 Ill.2d at 519-20, 261 Ill.Dec. 763, 764 N.E.2d 54, quoting Peile, 163 Ill.2d at 335, 206 Ill.Dec. 179, 645 N.E.2d 184, quoting Peile v. Skelgas, Inc., 242 Ill.App.

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Peile, 163 Ill. 2d at 335: 'Justice Lewis aptly notes that "[t]he battle over the forum results in a battle over minutiae."'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0335: Peile v. Skelgas, Inc., 242 Ill. App. 3d 500, 610 N.E.2d 813 (5th Dist. 1993) (Lewis, J., specially concurring)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 10.

Authority type: case; as written: 242 Ill.App.3d 500, 522; pincite: 522.

Cited for: 763, 764 N.E.2d 54, quoting Peile, 163 Ill.2d at 335, 206 Ill.Dec. 179, 645 N.E.2d 184, quoting Peile v. Skelgas, Inc.,

Quotes: []

Context: ine, 198 Ill.2d at 519-20, 261 Ill.Dec. 763, 764 N.E.2d 54, quoting Peile, 163 Ill.2d at 335, 206 Ill.Dec. 179, 645 N.E.2d 184, quoting Peile v. Skelgas, Inc., 242 Ill.App.3d 500, 522, 182 Ill.Dec. 944, 610 N.E.2d 813 (1993) (Lewis, J., specially concurring). As

Fictional by design: False; 

### First check: VERIFIED

Quoted sentence located in the appellate special concurrence on CourtListener.

Excerpt read: Lewis special concurrence: 'The battle over the forum results in a battle over minutiae.'

- https://www.courtlistener.com/opinion/2110774/peile-v-skelgas-inc/

### Second check: not required


## FNC-0336: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 10.

Authority type: case; as written: 198 Ill.2d at 525; pincite: 525.

Cited for: Today, convenience-the touchstone of the forum non conveniens doctrine-has a different meaning.” Guerine,

Quotes: []

Context: airways, telecommunications, and the world wide web. Today, convenience-the touchstone of the forum non conveniens doctrine-has a different meaning.” Guerine, 198 Ill.2d at 525, 261 Ill.Dec. 763, 764 N.E.2d 54. In considering the public interest factors, C

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 525 (CourtListener 3134965): 'the plaintiffs' negligence claim against Guerine has a local flavor. The plaintiffs' products liability claim against J.Q. Tex, however, is less localized. ... We live in a smaller world'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0337: 735 ILCS 5/2-102(a) (corporate residence for venue)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 10.

Authority type: statute; as written: 735 ILCS 5/2-102(a); pincite: .

Cited for: Clair County, with approximately eight trains per day passing the Langenhorst property in Clinton County and entering St. Clair County on the same railroad line. See

Quotes: []

Context: County, with approximately eight trains per day passing the Langenhorst property in Clinton County and entering St. Clair County on the same railroad line. See 735 ILCS 5/2-102(a) (West 2000) (in the case of a foreign corporation, residence is defined as any

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session. (The opinion cites an earlier West edition; current text read, provision unchanged in substance.)

Excerpt read: 'any foreign corporation authorized to transact business in this State is a resident of any county in which it has its registered office or other office or is doing business.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073500050K2-102.htm

### Second check: not required


## FNC-0338: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 10.

Authority type: case; as written: 198 Ill.2d at 525; pincite: 525.

Cited for: Clair County, particularly when one of the defendants is a “resident” of St. Clair County. See Guerine,

Quotes: []

Context: County is also not required by the court docket of St. Clair County, particularly when one of the defendants is a “resident” of St. Clair County. See Guerine, 198 Ill.2d at 525, 261 Ill.Dec. 763, 764 N.E.2d 54. Moreover, in ruling on defendants' motion, th

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 525 (CourtListener 3134965): 'the plaintiffs' negligence claim against Guerine has a local flavor. The plaintiffs' products liability claim against J.Q. Tex, however, is less localized. ... We live in a smaller world'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0339: Boner v. Peabody Coal Co., 142 Ill. 2d 523, 568 N.E.2d 883 (1991)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 142 Ill.2d at 538-39; pincite: 538-39.

Cited for: When deciding forum non conveniens issues, the trial court is in the better position to assess the burdens on its own docket. Boner,

Quotes: []

Context: s case in a timely manner. When deciding forum non conveniens issues, the trial court is in the better position to assess the burdens on its own docket. Boner, 142 Ill.2d at 538-39, 154 Ill.Dec. 662, 568 N.E.2d 883. “Court congestion is a relatively insignific

Fictional by design: False; 

### First check: VERIFIED

Boner text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Boner, 142 Ill. 2d at 538-39: 'a trial court is in a better position than a reviewing court to assess the burdens on its own docket.'

- https://www.courtlistener.com/opinion/2094308/boner-v-peabody-coal-co/

### Second check: not required


## FNC-0340: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 198 Ill.2d at 517; pincite: 517.

Cited for: “Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly.” Guerine,

Quotes: []

Context: Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly.” Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54, citing Brummett v. Wepfer Marine, Inc., 111 I

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 517 (CourtListener 3134965): 'Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly. ... The plaintiff has a substantial interest in choosing the forum where his rights will be vindicated'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0341: Brummett v. Wepfer Marine, Inc., 111 Ill. 2d 495, 490 N.E.2d 694 (1986)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 111 Ill.2d 495, 503; pincite: 503.

Cited for: “Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly.” Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54, citing Brummett v. Wepfer Marine, Inc.,

Quotes: []

Context: show the other forum would resolve the case more quickly.” Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54, citing Brummett v. Wepfer Marine, Inc., 111 Ill.2d 495, 503, 95 Ill.Dec. 841, 490 N.E.2d 694 (1986). Here, defendants have not shown that t

Fictional by design: False; 

### First check: VERIFIED

Brummett passages read on CourtListener.

Excerpt read: 'Courts should be extremely reluctant to dismiss a case from the forum rei gestae merely because that forum's docket has a backlog; and this factor is entitled to almost no weight without evidence ...'

- https://www.courtlistener.com/opinion/2251509/brummett-v-wepfer-marine-inc/

### Second check: not required


## FNC-0342: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 198 Ill.2d at 517; pincite: 517.

Cited for: Absent factors strongly favoring transfer, plaintiff's substantial interest in choosing the forum where his or her rights will be vindicated should rarely be disturbed. See Guerine,

Quotes: []

Context: y favoring transfer, plaintiff's substantial interest in choosing the forum where his or her rights will be vindicated should rarely be disturbed. See Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54, citing Griffith, 136 Ill.2d at 106, 143 Ill.D

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 517 (CourtListener 3134965): 'Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly. ... The plaintiff has a substantial interest in choosing the forum where his rights will be vindicated'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0343: Griffith v. Mitsubishi Aircraft International, Inc., 136 Ill. 2d 101, 554 N.E.2d 209 (1990)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 136 Ill.2d at 106; pincite: 106.

Cited for: See Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54, citing Griffith,

Quotes: []

Context: forum where his or her rights will be vindicated should rarely be disturbed. See Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54, citing Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones, 93 Ill.2d at 372-73, 67 Ill.Dec. 118,

Fictional by design: False; 

### First check: VERIFIED

Griffith text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Griffith, 136 Ill. 2d at 106: 'A plaintiffs right to select the forum is a substantial one, and unless the factors weigh strongly in favor of transfer, "the plaintiffs choice of forum should rarely be disturbed."'

- https://www.courtlistener.com/opinion/2196019/griffith-v-mitsubishi-aircraft-international-inc/

### Second check: not required


## FNC-0344: Jones v. Searle Laboratories, 93 Ill. 2d 366, 444 N.E.2d 157 (1982)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 93 Ill.2d at 372-73; pincite: 372-73.

Cited for: 763, 764 N.E.2d 54, citing Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones,

Quotes: []

Context: ely be disturbed. See Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54, citing Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones, 93 Ill.2d at 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157; Gulf Oil, 330 U.S. at 508-09, 67 S.Ct. at 843

Fictional by design: False; 

### First check: VERIFIED

Jones passage read on CourtListener.

Excerpt read: Jones quotes Gulf Oil: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/2032797/jones-v-searle-laboratories/

### Second check: not required


## FNC-0345: Gulf Oil Corp. v. Gilbert, 330 U.S. 501 (1947)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 330 U.S. at 508-09; pincite: 508-09.

Cited for: Jones, 93 Ill.2d at 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157; Gulf Oil,

Quotes: []

Context: 63, 764 N.E.2d 54, citing Griffith, 136 Ill.2d at 106, 143 Ill.Dec. 274, 554 N.E.2d 209; Jones, 93 Ill.2d at 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157; Gulf Oil, 330 U.S. at 508-09, 67 S.Ct. at 843, 91 L.Ed. at 1062-63; Restatement (Second) of Conflict of Laws

Fictional by design: False; 

### First check: VERIFIED

Gulf Oil passage read on CourtListener.

Excerpt read: 'But unless the balance is strongly in favor of the defendant, the plaintiff's choice of forum should rarely be disturbed.'

- https://www.courtlistener.com/opinion/104393/gulf-oil-corp-v-gilbert/

### Second check: not required


## FNC-0346: Restatement (Second) of Conflict of Laws § 84 cmt. c (1971)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: restatement_or_treatise; as written: Restatement (Second) of Conflict of Laws § 84, Comment c; pincite: .

Cited for: Gulf Oil, 330 U.S. at 508-09, 67 S.Ct. at 843, 91 L.Ed. at 1062-63;

Quotes: []

Context: Ill.Dec. 274, 554 N.E.2d 209; Jones, 93 Ill.2d at 372-73, 67 Ill.Dec. 118, 444 N.E.2d 157; Gulf Oil, 330 U.S. at 508-09, 67 S.Ct. at 843, 91 L.Ed. at 1062-63; Restatement (Second) of Conflict of Laws § 84, Comment c (1971). As we have indicated, this standard does not foreclose legitimate trans

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The attached opinion reproduces the asserted Restatement language, and another court opinion independently quotes part of comment c, but I did not obtain the ALI Restatement (Second) of Conflict of Laws §84 comment c itself. A quotation in a judicial opinion corroborates the wording but does not satisfy this audit’s direct-source reading requirement.

Excerpt read: The judicial reproductions say plaintiff choice should not be disturbed except for weighty reasons and dismissal requires a suitable alternative forum; ALI source text not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf
- https://www.ali.org/publications/restatement-law-second/conflict-laws
- https://cases.justia.com/montana/supreme-court/2015-da-14-0465.pdf

### Second check: not required


## FNC-0347: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 198 Ill.2d at 521; pincite: 521.

Cited for: As we have indicated, this standard does not foreclose legitimate transfers when the balance of factors strongly favors litigation in another forum. Guerine,

Quotes: []

Context: . As we have indicated, this standard does not foreclose legitimate transfers when the balance of factors strongly favors litigation in another forum. Guerine, 198 Ill.2d at 521, 261 Ill.Dec. 763, 764 N.E.2d 54. With these principles in mind, we have evalua

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 521 (CourtListener 3134965): 'the battle over forum begins with the plaintiffs choice already in the lead. ... it does not foreclose legitimate transfers when the balance of factors strongly favors litigation in another forum.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0348: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 198 Ill.2d at 520; pincite: 520.

Cited for: This is not a case of exceptional circumstances where the interests of justice require a trial in a more convenient forum. See Guerine,

Quotes: []

Context: ith trial in this case. This is not a case of exceptional circumstances where the interests of justice require a trial in a more convenient forum. See Guerine, 198 Ill.2d at 520, 261 Ill.Dec. 763, 764 N.E.2d 54; Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 520 (CourtListener 3134965): ''discretionary power which should be exercised only in exceptional circumstances ...' In most instances, the plaintiffs initial choice of forum will prevail'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0349: Peile v. Skelgas, Inc., 163 Ill. 2d 323, 645 N.E.2d 184 (1994)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 163 Ill.2d at 335-36; pincite: 335-36.

Cited for: See Guerine, 198 Ill.2d at 520, 261 Ill.Dec. 763, 764 N.E.2d 54; Peile,

Quotes: []

Context: ircumstances where the interests of justice require a trial in a more convenient forum. See Guerine, 198 Ill.2d at 520, 261 Ill.Dec. 763, 764 N.E.2d 54; Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179, 645 N.E.2d 184; Torres, 98 Ill.2d at 346, 74 Ill.Dec. 880, 4

Fictional by design: False; 

### First check: VERIFIED

Peile read on CourtListener (majority and Harrison dissent); proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Peile, 163 Ill. 2d at 335-36: 'The doctrine that was activated in Torres was designed to give the courts "discretionary power which should be exercised only in exceptional circumstances ..." In most instances, the plaintiffs initial choice of forum will prevail'

- https://www.courtlistener.com/opinion/2127753/peile-v-skelgas-inc/

### Second check: not required


## FNC-0350: Torres v. Walsh, 98 Ill. 2d 338, 456 N.E.2d 601 (1983)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 98 Ill.2d at 346; pincite: 346.

Cited for: Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179, 645 N.E.2d 184; Torres,

Quotes: []

Context: more convenient forum. See Guerine, 198 Ill.2d at 520, 261 Ill.Dec. 763, 764 N.E.2d 54; Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179, 645 N.E.2d 184; Torres, 98 Ill.2d at 346, 74 Ill.Dec. 880, 456 N.E.2d 601. Nor is this a case where the trial court's de

Fictional by design: False; 

### First check: VERIFIED

Torres passages read on CourtListener (CourtListener lacks the 74 Ill. Dec. parallel, which is not a defect). Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Torres, 98 Ill. 2d at 346: 'the doctrine of forum non conveniens is a discretionary power which should be exercised only in exceptional circumstances when it has been shown that the interests of justice require a trial in a more convenient forum.'

- https://www.courtlistener.com/opinion/2103179/torres-v-walsh/

### Second check: not required


## FNC-0351: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 11.

Authority type: case; as written: 198 Ill.2d at 526; pincite: 526.

Cited for:  discretion in denying an intrastate forum non conveniens motion to transfer the case to an adjacent county when, as here, most of the potential trial witnesses are scattered and no single county enjoys a predominant connection to the litigation. See Guerine,

Quotes: []

Context: county when, as here, most of the potential trial witnesses are scattered and no single county enjoys a predominant connection to the litigation. See Guerine, 198 Ill.2d at 526, 261 Ill.Dec. 763, 764 N.E.2d 54. In fact, based on the location of the defenda

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 526 (CourtListener 3134965): 'a trial court abuses its discretion in granting an intrastate forum non conveniens motion to transfer venue where, as here, the potential trial witnesses are scattered among several counties, including the plaintiffs chosen forum, and no single county enjoys a predominant connection to the litigation.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0352: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 12.

Authority type: case; as written: 207 Ill.2d at 183-84; pincite: 183-84.

Cited for:  presented from those presented in Guerine and noted that Guerine was based on the totality of the circumstances. Dawdy,

Quotes: []

Context: presented from those presented in Guerine and noted that Guerine was based on the totality of the circumstances. Dawdy, 207 Ill.2d at 183-84, 278 Ill.Dec. 92, 797 N.E.2d 687. We recognize that the dissent would prefer to

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 183-84 (CourtListener 9819104): 'Plaintiff conceded at oral argument that Guerine was based on the totality of the circumstances of that case and did not alter forum non conveniens principles in Illinois.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0353: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 12.

Authority type: case; as written: 198 Ill.2d at 521; pincite: 521.

Cited for: We reiterate that the standard of review on a forum non conveniens motion is abuse of discretion, and defendants must meet a high burden of showing that the “balance of factors strongly favors litigation in another forum” (emphasis added) (Guerine,

Quotes: []

Context: cretion, and defendants must meet a high burden of showing that the “balance of factors strongly favors litigation in another forum” (emphasis added) (Guerine, 198 Ill.2d at 521, 261 Ill.Dec. 763, 764 N.E.2d 54), and our holding is compelled under that stan

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 521 (CourtListener 3134965): 'the battle over forum begins with the plaintiffs choice already in the lead. ... it does not foreclose legitimate transfers when the balance of factors strongly favors litigation in another forum.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0354: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 12.

Authority type: case; as written: 219 Ill.2d at 469; pincite: 469.

Cited for: The dissent even concludes that “the convenience of the parties does not strongly favor one venue over the other.”

Quotes: []

Context: ur holding is compelled under that standard. The dissent even concludes that “the convenience of the parties does not strongly favor one venue over the other.” 219 Ill.2d at 469, 302 Ill.Dec. at 386, 848 N.E.2d at 950 (Garman, J., dissenting, joined by Thom

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 469 (Garman, J., dissenting): 'Balancing these considerations, the convenience of the parties does not strongly favor one venue over the other.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0355: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 12 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d 167; pincite: .

Cited for: Less than three years ago, this court addressed the doctrine of forum non conveniens in Dawdy v. Union Pacific R.R. Co.,

Quotes: []

Context: ment of the appellate court. Affirmed. Less than three years ago, this court addressed the doctrine of forum non conveniens in Dawdy v. Union Pacific R.R. Co., 207 Ill.2d 167, 278 Ill.Dec. 92, 797 N.E.2d 687 (2003). Dawdy was decided in the wake of First

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Lead opinion (CourtListener 9819104) read in full, e.g. 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County' [207 Ill. 2d at 178].

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0356: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 12 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d 511; pincite: .

Cited for: Dawdy was decided in the wake of First American Bank v. Guerine,

Quotes: []

Context: ns in Dawdy v. Union Pacific R.R. Co., 207 Ill.2d 167, 278 Ill.Dec. 92, 797 N.E.2d 687 (2003). Dawdy was decided in the wake of First American Bank v. Guerine, 198 Ill.2d 511, 261 Ill.Dec. 763, 764 N.E.2d 54 (2002), another forum non conveniens decision.

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Ill. Reports text (CourtListener 3134965): 'First American Bank, as executor of Angel's estate ...'; N.E.2d text (2056494) caption 'FIRST NATIONAL BANK et al., Appellants, v. Richard GUERINE et al.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0357: Langenhorst v. Norfolk Southern Ry. Co., 354 Ill. App. 3d 1103, 822 N.E.2d 480 (5th Dist. 2004)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 12 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 354 Ill.App.3d 1103, 1109; pincite: 1109.

Cited for: gment of the circuit court on remand, the appellate court speculated that it would not have been “ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.”

Quotes: []

Context: dered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.” 354 Ill.App.3d 1103, 1109, 290 Ill.Dec. 895, 822 N.E.2d 480. Until today, Dawdy and Guerine did both repr

Fictional by design: False; 

### First check: VERIFIED

Appellate opinion read on CourtListener; the described holdings and reasoning located (jury view, attorneys' proximity, 'minuscule' inconvenience, 1% clearance difference, local interest, no abuse of discretion).

Excerpt read: 'we would not be ordered to reconsider a venue transfer question in light of both Dawdy and Guerine if the supreme court did not think both decisions still represented good law.'; 'The 1% difference in favor of Clinton County does not raise concern over St. Clair County court congestion.'

- https://www.courtlistener.com/opinion/2004830/langenhorst-v-norfolk-southern-railway-co/

### Second check: not required


## FNC-0358: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 12 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 169; pincite: 169.

Cited for: Divergence From Dawdy In Dawdy, the plaintiff, a resident of Greene County, was driving a tractor in Macoupin County when he collided with a truck operated by an employee of the Union Pacific Railroad Company (Union Pacific). Dawdy,

Quotes: []

Context: y, was driving a tractor in Macoupin County when he collided with a truck operated by an employee of the Union Pacific Railroad Company (Union Pacific). Dawdy, 207 Ill.2d at 169, 278 Ill.Dec. 92, 797 N.E.2d 687. The plaintiff filed a lawsuit against Union P

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 169 (CourtListener 9819104): 'Plaintiff sought damages for injuries sustained in a motor vehicle accident that occurred in Macoupin County.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0359: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 12 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 169; pincite: 169.

Cited for: truck, that Union Pacific negligently failed to train and supervise the employee, and that Union Pacific negligently failed to ensure that attachments on the truck would not extend beyond the width of the vehicle when it was operated on public streets. Dawdy,

Quotes: []

Context: ific negligently failed to ensure that attachments on the truck would not extend beyond the width of the vehicle when it was operated on public streets. Dawdy, 207 Ill.2d at 169, 278 Ill.Dec. 92, 797 N.E.2d 687. The employee was a resident of Macoupin Count

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 169 (CourtListener 9819104): 'Plaintiff sought damages for injuries sustained in a motor vehicle accident that occurred in Macoupin County.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0360: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 12 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 170; pincite: 170.

Cited for: 92, 797 N.E.2d 687. The employee was a resident of Macoupin County. Dawdy,

Quotes: []

Context: hicle when it was operated on public streets. Dawdy, 207 Ill.2d at 169, 278 Ill.Dec. 92, 797 N.E.2d 687. The employee was a resident of Macoupin County. Dawdy, 207 Ill.2d at 170, 278 Ill.Dec. 92, 797 N.E.2d 687. Union Pacific, a Delaware corporation with it

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 170 (CourtListener 9819104): 'Union Pacific is a Delaware corporation with its principal place of business in Omaha, Nebraska. ... Of the 18 witnesses who may be called to testify at trial, most of them reside in or near Macoupin County'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0361: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 170; pincite: 170.

Cited for:  Omaha, Nebraska, did business in both Macoupin County and Madison County and operated a facility in the latter. Dawdy,

Quotes: []

Context: Omaha, Nebraska, did business in both Macoupin County and Madison County and operated a facility in the latter. Dawdy, 207 Ill.2d at 170, 278 Ill.Dec. 92, 797 N.E.2d 687. The 18 potential witnesses resided in various

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 170 (CourtListener 9819104): 'Union Pacific is a Delaware corporation with its principal place of business in Omaha, Nebraska. ... Of the 18 witnesses who may be called to testify at trial, most of them reside in or near Macoupin County'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0362: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 170; pincite: 170.

Cited for: The 18 potential witnesses resided in various counties. Dawdy,

Quotes: []

Context: nd operated a facility in the latter. Dawdy, 207 Ill.2d at 170, 278 Ill.Dec. 92, 797 N.E.2d 687. The 18 potential witnesses resided in various counties. Dawdy, 207 Ill.2d at 170, 278 Ill.Dec. 92, 797 N.E.2d 687. The defendants filed a motion to transfer ven

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 170 (CourtListener 9819104): 'Union Pacific is a Delaware corporation with its principal place of business in Omaha, Nebraska. ... Of the 18 witnesses who may be called to testify at trial, most of them reside in or near Macoupin County'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0363: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 170; pincite: 170.

Cited for: The defendants filed a motion to transfer venue from Madison County to Macoupin County under the doctrine of forum non conveniens, which the circuit court denied. Dawdy,

Quotes: []

Context: ants filed a motion to transfer venue from Madison County to Macoupin County under the doctrine of forum non conveniens, which the circuit court denied. Dawdy, 207 Ill.2d at 170, 278 Ill.Dec. 92, 797 N.E.2d 687. On appeal, the appellate court affirmed the j

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 170 (CourtListener 9819104): 'Union Pacific is a Delaware corporation with its principal place of business in Omaha, Nebraska. ... Of the 18 witnesses who may be called to testify at trial, most of them reside in or near Macoupin County'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0364: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 171; pincite: 171.

Cited for: On appeal, the appellate court affirmed the judgment of the circuit court. Dawdy,

Quotes: []

Context: cuit court denied. Dawdy, 207 Ill.2d at 170, 278 Ill.Dec. 92, 797 N.E.2d 687. On appeal, the appellate court affirmed the judgment of the circuit court. Dawdy, 207 Ill.2d at 171, 278 Ill.Dec. 92, 797 N.E.2d 687. In reversing, this court balanced the private

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 171 (CourtListener 9819104): 'on plaintiff's motion for rehearing, the appellate court vacated its decision and affirmed the circuit court's denial of defendant's motion to transfer venue.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0365: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 185; pincite: 185.

Cited for: In reversing, this court balanced the private and public interest factors relevant to the forum non conveniens analysis and concluded that the circuit court abused its discretion in denying the defendant's motion to transfer. Dawdy,

Quotes: []

Context: relevant to the forum non conveniens analysis and concluded that the circuit court abused its discretion in denying the defendant's motion to transfer. Dawdy, 207 Ill.2d at 185, 278 Ill.Dec. 92, 797 N.E.2d 687. With respect to the private interest factors,

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 185 (CourtListener 9819104): 'we hold that the circuit court abused its discretion in denying defendants' motion to transfer venue from Madison County to Macoupin County'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0366: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 177; pincite: 177.

Cited for: With respect to the private interest factors, we initially examined the relative ease of access to testimonial evidence. Dawdy,

Quotes: []

Context: 78 Ill.Dec. 92, 797 N.E.2d 687. With respect to the private interest factors, we initially examined the relative ease of access to testimonial evidence. Dawdy, 207 Ill.2d at 177, 278 Ill.Dec. 92, 797 N.E.2d 687. Two of the potential witnesses resided in Mac

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 177 (CourtListener 9819104): 'An abuse of discretion will be found where no reasonable person would take the view adopted by the trial court.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0367: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 178; pincite: 178.

Cited for: Two of the potential witnesses resided in Macoupin County, none resided in Madison County, and on the whole, the potential witnesses resided closer to Macoupin County than to Madison County. Dawdy,

Quotes: []

Context: in Macoupin County, none resided in Madison County, and on the whole, the potential witnesses resided closer to Macoupin County than to Madison County. Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. Therefore, we concluded that, insofar as ease

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 178 (CourtListener 9819104): 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County. ... This convenience factor is not concerned with the necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0368: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 178; pincite: 178.

Cited for: Therefore, we concluded that, insofar as ease of access to testimonial evidence was concerned, Macoupin County was a slightly more convenient venue than Madison County. Dawdy,

Quotes: []

Context: ncluded that, insofar as ease of access to testimonial evidence was concerned, Macoupin County was a slightly more convenient venue than Madison County. Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. We next turned to the possibility of viewing

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 178 (CourtListener 9819104): 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County. ... This convenience factor is not concerned with the necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0369: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 178; pincite: 178.

Cited for: We next turned to the possibility of viewing the premises of the accident. Dawdy,

Quotes: []

Context: an Madison County. Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. We next turned to the possibility of viewing the premises of the accident. Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. The appellate court apparently had given this

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 178 (CourtListener 9819104): 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County. ... This convenience factor is not concerned with the necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0370: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 178; pincite: 178.

Cited for: The appellate court apparently had given this factor no weight, concluding that although the accident occurred in Macoupin County, there was nothing in the record to indicate that a view of the accident site would be necessary. Dawdy,

Quotes: []

Context: that although the accident occurred in Macoupin County, there was nothing in the record to indicate that a view of the accident site would be necessary. Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. We emphasized that the convenience factor of

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 178 (CourtListener 9819104): 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County. ... This convenience factor is not concerned with the necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0371: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 178; pincite: 178.

Cited for: sized that the convenience factor of viewing the premises of the accident “is not concerned with the necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.” (Emphases in original.) Dawdy,

Quotes: []

Context: necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.” (Emphases in original.) Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. Accordingly, we determined that if the trial

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 178 (CourtListener 9819104): 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County. ... This convenience factor is not concerned with the necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0372: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 179; pincite: 179.

Cited for: Accordingly, we determined that if the trial court were later to decide that viewing the accident site would be appropriate, it would not make sense for a jury composed of Madison County residents to travel to Macoupin County to do so. Dawdy,

Quotes: []

Context: g the accident site would be appropriate, it would not make sense for a jury composed of Madison County residents to travel to Macoupin County to do so. Dawdy, 207 Ill.2d at 179, 278 Ill.Dec. 92, 797 N.E.2d 687. Finally, we assessed other practical consider

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 179 (CourtListener 9819104): 'the necessity or propriety of viewing the scene is a decision left within the discretion of the trial court. ... While a court may consider this factor, "little weight should be accorded it."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0373: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 179; pincite: 179.

Cited for: Finally, we assessed other practical considerations that would make trying the case easy, expeditious, and inexpensive. Dawdy,

Quotes: []

Context: 278 Ill.Dec. 92, 797 N.E.2d 687. Finally, we assessed other practical considerations that would make trying the case easy, expeditious, and inexpensive. Dawdy, 207 Ill.2d at 179, 278 Ill.Dec. 92, 797 N.E.2d 687. In doing so, we accorded “little weight” to t

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 179 (CourtListener 9819104): 'the necessity or propriety of viewing the scene is a decision left within the discretion of the trial court. ... While a court may consider this factor, "little weight should be accorded it."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0374: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 179; pincite: 179.

Cited for: In doing so, we accorded “little weight” to the locations of the offices of the parties' attorneys, which were situated in Madison County and neighboring St. Clair County. Dawdy,

Quotes: []

Context: orded “little weight” to the locations of the offices of the parties' attorneys, which were situated in Madison County and neighboring St. Clair County. Dawdy, 207 Ill.2d at 179, 278 Ill.Dec. 92, 797 N.E.2d 687. We also declined to accept the contention tha

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 179 (CourtListener 9819104): 'the necessity or propriety of viewing the scene is a decision left within the discretion of the trial court. ... While a court may consider this factor, "little weight should be accorded it."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0375: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 180; pincite: 180.

Cited for: We also declined to accept the contention that since Madison County is adjacent to Macoupin County, Madison County conclusively could not be an inconvenient venue for the defendants. Dawdy,

Quotes: []

Context: contention that since Madison County is adjacent to Macoupin County, Madison County conclusively could not be an inconvenient venue for the defendants. Dawdy, 207 Ill.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687. Turning to the public interest factors, we fi

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 180 (CourtListener 9819104): 'We cannot accept the contention that trial in an adjacent county is conclusively not inconvenient for a defendant. ... no single forum non conveniens factor should be accorded central emphasis or conclusive effect.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0376: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 181; pincite: 181.

Cited for: Turning to the public interest factors, we first examined court congestion. Dawdy,

Quotes: []

Context: r the defendants. Dawdy, 207 Ill.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687. Turning to the public interest factors, we first examined court congestion. Dawdy, 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687. The 1998 annual report of the Administrative

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 181 (CourtListener 9819104): 'The court congestion factor, by itself, is relatively insignificant ... there were 1,867 jury actions for damages in excess of $50,000 pending in Madison County, while only 137 ... "crowded to the point where congestion is of great concern."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0377: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 13 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 181; pincite: 181.

Cited for: The 1998 annual report of the Administrative Office of the Illinois Courts indicated that there were 1,867 jury actions for damages in excess of $50,000 pending in Madison County, and only 137 comparable actions pending in Macoupin County. Dawdy,

Quotes: []

Context: at there were 1,867 jury actions for damages in excess of $50,000 pending in Madison County, and only 137 comparable actions pending in Macoupin County. Dawdy, 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687. Moreover, the average time between filing and

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 181 (CourtListener 9819104): 'The court congestion factor, by itself, is relatively insignificant ... there were 1,867 jury actions for damages in excess of $50,000 pending in Madison County, while only 137 ... "crowded to the point where congestion is of great concern."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0378: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 181; pincite: 181.

Cited for: 

Quotes: []

Context: 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687. Thus, Madison County's docket was significant

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 181 (CourtListener 9819104): 'The court congestion factor, by itself, is relatively insignificant ... there were 1,867 jury actions for damages in excess of $50,000 pending in Madison County, while only 137 ... "crowded to the point where congestion is of great concern."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0379: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 181; pincite: 181.

Cited for: Thus, Madison County's docket was significantly more congested than that of Macoupin County. Dawdy,

Quotes: []

Context: 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687. Thus, Madison County's docket was significantly more congested than that of Macoupin County. Dawdy, 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687. Next, we discussed the nature and extent of l

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 181 (CourtListener 9819104): 'The court congestion factor, by itself, is relatively insignificant ... there were 1,867 jury actions for damages in excess of $50,000 pending in Madison County, while only 137 ... "crowded to the point where congestion is of great concern."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0380: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 181-82; pincite: 181-82.

Cited for: Next, we discussed the nature and extent of local interests in deciding the controversy. Dawdy,

Quotes: []

Context: nty. Dawdy, 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687. Next, we discussed the nature and extent of local interests in deciding the controversy. Dawdy, 207 Ill.2d at 181-82, 278 Ill.Dec. 92, 797 N.E.2d 687. The facts Union Pacific conducted business in

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 181-82 (CourtListener 9819104): 'Another public interest factor concerns the local interest in local controversies.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0381: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 182; pincite: 182.

Cited for: The facts Union Pacific conducted business in Madison County and its employee maintained a post office box there were not dispositive of this aspect of the forum non conveniens analysis. Dawdy,

Quotes: []

Context: business in Madison County and its employee maintained a post office box there were not dispositive of this aspect of the forum non conveniens analysis. Dawdy, 207 Ill.2d at 182, 278 Ill.Dec. 92, 797 N.E.2d 687. Rather, we found it significant that the acci

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 182 (CourtListener 9819104): 'It is assumed on a forum non conveniens motion that the plaintiffs chosen forum is a proper venue for the action. ... the fact that the defendant conducts business within Madison County is not a dispositive factor in this case.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0382: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 183; pincite: 183.

Cited for: and that some of the witnesses resided in Macoupin County. Dawdy,

Quotes: []

Context: itnesses were, in general, unconnected to Madison County, despite the fact some worked there; and that some of the witnesses resided in Macoupin County. Dawdy, 207 Ill.2d at 183, 278 Ill.Dec. 92, 797 N.E.2d 687. Accordingly, we concluded that Madison County

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 183 (CourtListener 9819104): 'Clearly, Madison County has little or no interest in trying the action of a nonresident whose claim arose in Macoupin County. ... Most significantly, the fact that the accident occurred in Macoupin County gives the action a local interest.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0383: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 183; pincite: 183.

Cited for: Accordingly, we concluded that Madison County had “little or no interest” in trying the action, and that Macoupin County, on the contrary, had a “strong connection with and interest in” the action. Dawdy,

Quotes: []

Context: had “little or no interest” in trying the action, and that Macoupin County, on the contrary, had a “strong connection with and interest in” the action. Dawdy, 207 Ill.2d at 183, 278 Ill.Dec. 92, 797 N.E.2d 687. Finally, we examined the relative propriety o

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 183 (CourtListener 9819104): 'Clearly, Madison County has little or no interest in trying the action of a nonresident whose claim arose in Macoupin County. ... Most significantly, the fact that the accident occurred in Macoupin County gives the action a local interest.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0384: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 183; pincite: 183.

Cited for: Finally, we examined the relative propriety of imposing jury duty on the residents of Madison County and Macoupin County. Dawdy,

Quotes: []

Context: 8 Ill.Dec. 92, 797 N.E.2d 687. Finally, we examined the relative propriety of imposing jury duty on the residents of Madison County and Macoupin County. Dawdy, 207 Ill.2d at 183, 278 Ill.Dec. 92, 797 N.E.2d 687. With respect to this consideration, we conclu

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 183 (CourtListener 9819104): 'Clearly, Madison County has little or no interest in trying the action of a nonresident whose claim arose in Macoupin County. ... Most significantly, the fact that the accident occurred in Macoupin County gives the action a local interest.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0385: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 183; pincite: 183.

Cited for: With respect to this consideration, we concluded that Madison County residents should not be burdened with jury duty, given that the action did not arise in, and had no relation to, their county. Dawdy,

Quotes: []

Context: luded that Madison County residents should not be burdened with jury duty, given that the action did not arise in, and had no relation to, their county. Dawdy, 207 Ill.2d at 183, 278 Ill.Dec. 92, 797 N.E.2d 687. Relatedly, we reasoned it would not be unfair

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 183 (CourtListener 9819104): 'Clearly, Madison County has little or no interest in trying the action of a nonresident whose claim arose in Macoupin County. ... Most significantly, the fact that the accident occurred in Macoupin County gives the action a local interest.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0386: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 183; pincite: 183.

Cited for: Relatedly, we reasoned it would not be unfair to burden the residents of Macoupin County with jury duty, given Macoupin County's significant interest in the dispute. Dawdy,

Quotes: []

Context: reasoned it would not be unfair to burden the residents of Macoupin County with jury duty, given Macoupin County's significant interest in the dispute. Dawdy, 207 Ill.2d at 183, 278 Ill.Dec. 92, 797 N.E.2d 687. After individually considering the private an

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 183 (CourtListener 9819104): 'Clearly, Madison County has little or no interest in trying the action of a nonresident whose claim arose in Macoupin County. ... Most significantly, the fact that the accident occurred in Macoupin County gives the action a local interest.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0387: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 184; pincite: 184.

Cited for:  considering the private and public interest factors relevant to the forum non conveniens analysis, we concluded that the weight of the public interest factors “greatly” favored Macoupin County, and that the private interest factors favored it as well. Dawdy,

Quotes: []

Context: we concluded that the weight of the public interest factors “greatly” favored Macoupin County, and that the private interest factors favored it as well. Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687. We also noted that the deference we would acc

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 184 (CourtListener 9819104): 'In this case, however, none of the witnesses reside in Madison County and Macoupin County has a predominant connection to this case. ... the balance of factors strongly favors transfer to Macoupin County.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0388: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 184; pincite: 184.

Cited for: We also noted that the deference we would accord to the plaintiff's choice of venue was reduced, because he did not reside there, and his cause of action did not arise there. Dawdy,

Quotes: []

Context: deference we would accord to the plaintiff's choice of venue was reduced, because he did not reside there, and his cause of action did not arise there. Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687. In light of these considerations, we held “th

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 184 (CourtListener 9819104): 'In this case, however, none of the witnesses reside in Madison County and Macoupin County has a predominant connection to this case. ... the balance of factors strongly favors transfer to Macoupin County.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0389: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 184; pincite: 184.

Cited for: In light of these considerations, we held “the balance of factors strongly favor[ed] transfer to Macoupin County” (Dawdy,

Quotes: []

Context: 184, 278 Ill.Dec. 92, 797 N.E.2d 687. In light of these considerations, we held “the balance of factors strongly favor[ed] transfer to Macoupin County” (Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687), and the circuit court abused its discretion

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 184 (CourtListener 9819104): 'In this case, however, none of the witnesses reside in Madison County and Macoupin County has a predominant connection to this case. ... the balance of factors strongly favors transfer to Macoupin County.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0390: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 185; pincite: 185.

Cited for: 92, 797 N.E.2d 687), and the circuit court abused its discretion in denying the defendants' motion to transfer venue (Dawdy,

Quotes: []

Context: y, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687), and the circuit court abused its discretion in denying the defendants' motion to transfer venue (Dawdy, 207 Ill.2d at 185, 278 Ill.Dec. 92, 797 N.E.2d 687). The majority disregards significant aspects

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 185 (CourtListener 9819104): 'we hold that the circuit court abused its discretion in denying defendants' motion to transfer venue from Madison County to Macoupin County'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0391: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 178; pincite: 178.

Cited for: Initially, the majority ignores Dawdy's conclusion that the possibility of viewing the accident site, not the necessity of doing so, is the relevant consideration in weighing this factor. Dawdy,

Quotes: []

Context: dy's conclusion that the possibility of viewing the accident site, not the necessity of doing so, is the relevant consideration in weighing this factor. Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. As we noted in Dawdy, “the necessity or propr

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 178 (CourtListener 9819104): 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County. ... This convenience factor is not concerned with the necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0392: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 179; pincite: 179.

Cited for: As we noted in Dawdy, “the necessity or propriety of viewing the scene is a decision left within the discretion of the trial court.” Dawdy,

Quotes: []

Context: 92, 797 N.E.2d 687. As we noted in Dawdy, “the necessity or propriety of viewing the scene is a decision left within the discretion of the trial court.” Dawdy, 207 Ill.2d at 179, 278 Ill.Dec. 92, 797 N.E.2d 687. The majority concludes that “a view of the ac

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 179 (CourtListener 9819104): 'the necessity or propriety of viewing the scene is a decision left within the discretion of the trial court. ... While a court may consider this factor, "little weight should be accorded it."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0393: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 14 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 448-49; pincite: 448-49.

Cited for: The majority concludes that “a view of the accident site is not appropriate,” reasoning that the conditions alleged to have caused the accident no longer exist, so a jury view of the site as it existed on the date of the accident is not possible.

Quotes: []

Context: that the conditions alleged to have caused the accident no longer exist, so a jury view of the site as it existed on the date of the accident is not possible. 219 Ill.2d at 448-49, 302 Ill.Dec. at 374, 848 N.E.2d at 938. This conclusion is not ours to make. I

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 448-49: 'although the accident occurred in Clinton County, a view of the accident site is not appropriate.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0394: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 15 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 449; pincite: 449.

Cited for: Clair County are completely irrelevant to whether a jury view of the accident site might be appropriate.

Quotes: []

Context: and the location of his investigation materials in St. Clair County are completely irrelevant to whether a jury view of the accident site might be appropriate. 219 Ill.2d at 449, 302 Ill.Dec. at 374, 848 N.E.2d at 938. Next, in evaluating the relative ease

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 449: 'Defendants have therefore failed to show that trial in Clinton County would be more convenient than St. Clair County for most of the witnesses.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0395: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 15 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 178; pincite: 178.

Cited for: s mentioned, in Dawdy, we focused primarily on the facts that two of the potential witnesses resided in Macoupin County, none resided in Madison County, and on the whole, the potential witnesses resided closer to Macoupin County than to Madison County. Dawdy,

Quotes: []

Context: in Macoupin County, none resided in Madison County, and on the whole, the potential witnesses resided closer to Macoupin County than to Madison County. Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. In this case, the majority concludes that def

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 178 (CourtListener 9819104): 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County. ... This convenience factor is not concerned with the necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0396: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 15 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 449; pincite: 449.

Cited for: In this case, the majority concludes that defendants “failed to show that trial in Clinton County would be more convenient than St. Clair County for most of the witnesses” (

Quotes: []

Context: the majority concludes that defendants “failed to show that trial in Clinton County would be more convenient than St. Clair County for most of the witnesses” (219 Ill.2d at 449, 302 Ill.Dec. at 374, 848 N.E.2d at 938) without once mentioning that six witne

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 449: 'Defendants have therefore failed to show that trial in Clinton County would be more convenient than St. Clair County for most of the witnesses.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0397: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217, 506 N.E.2d 1291 (1987)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 16 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 116 Ill.2d 217, 227; pincite: 227.

Cited for: ir County residency of plaintiff's investigator should be heavily discounted since plaintiff hired the investigator after the accident to perform services on her behalf, presumably in contemplation of litigation. See, e.g., Bland v. Norfolk & Western Ry. Co.,

Quotes: []

Context: he investigator after the accident to perform services on her behalf, presumably in contemplation of litigation. See, e.g., Bland v. Norfolk & Western Ry. Co., 116 Ill.2d 217, 227, 107 Ill.Dec. 236, 506 N.E.2d 1291 (1987) (noting that undue weight should not

Fictional by design: False; 

### First check: VERIFIED

Bland text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Bland, 116 Ill. 2d at 227: 'To do so would allow a plaintiff to easily frustrate the forum non conveniens principle by selecting as a witness a treating physician or expert in what would, in reality, be an inconvenient forum.'

- https://www.courtlistener.com/opinion/2210166/bland-v-norfolk-western-railway-co/

### Second check: not required


## FNC-0398: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 16 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 180; pincite: 180.

Cited for: Specifically, the majority ignores our refusal in Dawdy to “accept the contention that trial in an adjacent county is conclusively not inconvenient for a defendant” (Dawdy,

Quotes: []

Context: the majority ignores our refusal in Dawdy to “accept the contention that trial in an adjacent county is conclusively not inconvenient for a defendant” (Dawdy, 207 Ill.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687), stating that it “discern[s] no inconvenience

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 180 (CourtListener 9819104): 'We cannot accept the contention that trial in an adjacent county is conclusively not inconvenient for a defendant. ... no single forum non conveniens factor should be accorded central emphasis or conclusive effect.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0399: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 16 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 450; pincite: 450.

Cited for: Clair Counties are adjacent, and travel distances for likely witnesses are minimally different” (

Quotes: []

Context: ants to try this case in St. Clair County when Clinton and St. Clair Counties are adjacent, and travel distances for likely witnesses are minimally different” (219 Ill.2d at 450, 302 Ill.Dec. at 374, 848 N.E.2d at 938). The fact the counties are adjacent to

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 450: 'We discern no inconvenience for the defendants to try this case in St. Clair County when Clinton and St. Clair Counties are adjacent'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0400: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 16 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 182; pincite: 182.

Cited for: In Dawdy, with respect to the local interests in deciding the controversy, we declined to attach dispositive significance to the fact the corporate defendant did business in the county where the lawsuit was filed. Dawdy,

Quotes: []

Context: controversy, we declined to attach dispositive significance to the fact the corporate defendant did business in the county where the lawsuit was filed. Dawdy, 207 Ill.2d at 182, 278 Ill.Dec. 92, 797 N.E.2d 687 (“the fact that the defendant conducts busines

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 182 (CourtListener 9819104): 'It is assumed on a forum non conveniens motion that the plaintiffs chosen forum is a proper venue for the action. ... the fact that the defendant conducts business within Madison County is not a dispositive factor in this case.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0401: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 16 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 451; pincite: 451.

Cited for: Clair County]” and that “Norfolk railroad tracks traverse all of St. Clair County.”

Quotes: []

Context: es that “Norfolk * * * has its registered agent for service located in [St. Clair County]” and that “Norfolk railroad tracks traverse all of St. Clair County.” 219 Ill.2d at 451, 302 Ill.Dec. at 375, 848 N.E.2d at 939. According to the majority, “St. Clair

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 451: 'it specifically noted that it would have no difficulty trying this case in a timely manner.'; 'Norfolk railroad tracks traverse all of St. Clair County'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0402: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 16 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 451; pincite: 451.

Cited for: Clair County and this same railway line bisects all of St. Clair County.”

Quotes: []

Context: y true when, as here, the defendant railroad maintains similar rural crossings in St. Clair County and this same railway line bisects all of St. Clair County.” 219 Ill.2d at 451, 302 Ill.Dec. at 375, 848 N.E.2d at 939. This reasoning is misguided. The mere

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 451: 'it specifically noted that it would have no difficulty trying this case in a timely manner.'; 'Norfolk railroad tracks traverse all of St. Clair County'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0403: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 16 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 183; pincite: 183.

Cited for: and that some of the witnesses resided in the transferee county. See Dawdy,

Quotes: []

Context: hat the witnesses were, in general, unconnected to the county where suit was filed; and that some of the witnesses resided in the transferee county. See Dawdy, 207 Ill.2d at 183, 278 Ill.Dec. 92, 797 N.E.2d 687. We placed particular emphasis on the fact the

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 183 (CourtListener 9819104): 'Clearly, Madison County has little or no interest in trying the action of a nonresident whose claim arose in Macoupin County. ... Most significantly, the fact that the accident occurred in Macoupin County gives the action a local interest.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0404: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 16 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 183; pincite: 183.

Cited for: We placed particular emphasis on the fact the accident occurred in the transferee county. Dawdy,

Quotes: []

Context: See Dawdy, 207 Ill.2d at 183, 278 Ill.Dec. 92, 797 N.E.2d 687. We placed particular emphasis on the fact the accident occurred in the transferee county. Dawdy, 207 Ill.2d at 183, 278 Ill.Dec. 92, 797 N.E.2d 687 (“Most significantly, the fact

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 183 (CourtListener 9819104): 'Clearly, Madison County has little or no interest in trying the action of a nonresident whose claim arose in Macoupin County. ... Most significantly, the fact that the accident occurred in Macoupin County gives the action a local interest.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0405: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 17 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 169-70; pincite: 169-70.

Cited for: In Dawdy, the plaintiff was a resident of Greene County, suit was filed in Madison County, and the defendants wished to transfer venue to Macoupin County. Dawdy,

Quotes: []

Context: Dawdy, the plaintiff was a resident of Greene County, suit was filed in Madison County, and the defendants wished to transfer venue to Macoupin County. Dawdy, 207 Ill.2d at 169-70, 278 Ill.Dec. 92, 797 N.E.2d 687. Here, plaintiff resides in Clinton County, su

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 169-70 (CourtListener 9819104): 'Plaintiff resides in Greene County. The action arose in Macoupin County. Riederer resides in Macoupin County.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0406: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 17 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 183; pincite: 183.

Cited for: I would briefly note that whether it is appropriate to impose jury duty on the residents of a county is related to the strength of a county's local interest in a controversy. See, e.g., Dawdy,

Quotes: []

Context: it is appropriate to impose jury duty on the residents of a county is related to the strength of a county's local interest in a controversy. See, e.g., Dawdy, 207 Ill.2d at 183, 278 Ill.Dec. 92, 797 N.E.2d 687. The majority finds it unproblematic that “St.

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 183 (CourtListener 9819104): 'Clearly, Madison County has little or no interest in trying the action of a nonresident whose claim arose in Macoupin County. ... Most significantly, the fact that the accident occurred in Macoupin County gives the action a local interest.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0407: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 17 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 451; pincite: 451.

Cited for: Clair County residents will bear the burden of jury duty and trial expense” in this case.

Quotes: []

Context: ec. 92, 797 N.E.2d 687. The majority finds it unproblematic that “St. Clair County residents will bear the burden of jury duty and trial expense” in this case. 219 Ill.2d at 451, 302 Ill.Dec. at 375, 848 N.E.2d at 939. However, because plaintiff's action di

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 451: 'it specifically noted that it would have no difficulty trying this case in a timely manner.'; 'Norfolk railroad tracks traverse all of St. Clair County'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0408: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 17 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 451-52; pincite: 451-52.

Cited for: Finally, in assessing court congestion, the majority fails to examine the statistical criteria we considered in Dawdy and instead focuses solely on the circuit court judge's assessment of the St. Clair County circuit court's docket.

Quotes: []

Context: statistical criteria we considered in Dawdy and instead focuses solely on the circuit court judge's assessment of the St. Clair County circuit court's docket. 219 Ill.2d at 451-52, 302 Ill.Dec. at 375-76, 848 N.E.2d at 939-40. In Dawdy, we looked to the overa

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 451-52: 'When deciding forum non conveniens issues, the trial court is in the better position to assess the burdens on its own docket.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0409: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 17 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 181; pincite: 181.

Cited for: In Dawdy, we looked to the overall number of pending jury actions for damages over $50,000 and the time to verdict for such actions in determining that Madison County's docket was significantly more congested than that of Macoupin County. Dawdy,

Quotes: []

Context: ,000 and the time to verdict for such actions in determining that Madison County's docket was significantly more congested than that of Macoupin County. Dawdy, 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687. Here, the 2000 annual report of the Administr

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 181 (CourtListener 9819104): 'The court congestion factor, by itself, is relatively insignificant ... there were 1,867 jury actions for damages in excess of $50,000 pending in Madison County, while only 137 ... "crowded to the point where congestion is of great concern."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0410: Administrative Office of the Illinois Courts, 2000 Annual Report of the Illinois Courts, Statistical Summary

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 17.

Authority type: other; as written: Administrative Office of the Illinois Courts, 2000 Annual Report of the Illinois Courts, Statistical Summary 19, 28; pincite: .

Cited for: Administrative Office of the Illinois Courts, 2000 Annual Report of the Illinois Courts,

Quotes: []

Context: lair County, but only 37 comparable actions pending in Clinton County. Administrative Office of the Illinois Courts, 2000 Annual Report of the Illinois Courts, Statistical Summary 19, 28. Moreover, the average time between filing and verdict in such cases was 31.9 m

Fictional by design: False; 

### First check: VERIFIED

Visually inspected the official 2000 Administrative Office Statistical Summary. Printed pages 19 and 28 (PDF pages 26 and 35) show 37 pending Law > $50,000 jury matters in Clinton and 423 in St. Clair. This is a statistical claim in the Langenhorst dissent, not the majority holding.

Excerpt read: Clinton row, Law > $50k Jury, end pending: 37. St. Clair row, same column, end pending: 423.

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/c28abc8f-cbab-4477-b247-e1dfeab97fe5/2000%20Stat%20Summary.pdf

### Second check: not required


## FNC-0411: Administrative Office of the Illinois Courts, 2000 Annual Report of the Illinois Courts, Statistical Summary

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 17.

Authority type: other; as written: Administrative Office of the Illinois Courts, 2000 Annual Report of the Illinois Courts, Statistical Summary 56; pincite: .

Cited for: Clair County, but only 18 months in Clinton County. 2000 Annual Report of the Illinois Courts,

Quotes: []

Context: between filing and verdict in such cases was 31.9 months in St. Clair County, but only 18 months in Clinton County. 2000 Annual Report of the Illinois Courts, Statistical Summary 56. The majority offers no account of these statistics, content simply to state th

Fictional by design: False; 

### First check: VERIFIED

Visually inspected official printed page 56 (PDF page 63) of the 2000 Statistical Summary. It gives average filing-to-verdict time of 31.9 months for St. Clair and 18.0 months for Clinton in the cited Law > $50,000 jury category. Langenhorst states these in dissent.

Excerpt read: Time-lapse table, Law > $50k jury: St. Clair 31.9 months; Clinton 18.0 months.

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/c28abc8f-cbab-4477-b247-e1dfeab97fe5/2000%20Stat%20Summary.pdf

### Second check: not required


## FNC-0412: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 17 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 451; pincite: 451.

Cited for: Clair County circuit court “specifically noted that it would have no difficulty trying this case in a timely manner.”

Quotes: []

Context: ics, content simply to state that the St. Clair County circuit court “specifically noted that it would have no difficulty trying this case in a timely manner.” 219 Ill.2d at 451, 302 Ill.Dec. at 375, 848 N.E.2d at 939. In support of th is rationale, the maj

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 451: 'it specifically noted that it would have no difficulty trying this case in a timely manner.'; 'Norfolk railroad tracks traverse all of St. Clair County'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0413: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 17 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 451; pincite: 451.

Cited for: for the proposition that a circuit court is in a better position than a reviewing court to assess the burdens on its own docket.

Quotes: []

Context: ites Boner v. Peabody Coal Co. for the proposition that a circuit court is in a better position than a reviewing court to assess the burdens on its own docket. 219 Ill.2d at 451, 302 Ill.Dec. at 375, 848 N.E.2d at 939, citing

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 451: 'it specifically noted that it would have no difficulty trying this case in a timely manner.'; 'Norfolk railroad tracks traverse all of St. Clair County'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0414: Boner v. Peabody Coal Co., 142 Ill. 2d 523, 568 N.E.2d 883 (1991)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 142 Ill.2d at 538-39; pincite: 538-39.

Cited for:  Boner,

Quotes: []

Context: Boner, 142 Ill.2d at 538-39, 154 Ill.Dec. 662, 568 N.E.2d 883. This may be so, but it does not mean that a

Fictional by design: False; 

### First check: VERIFIED

Boner text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Boner, 142 Ill. 2d at 538-39: 'a trial court is in a better position than a reviewing court to assess the burdens on its own docket.'

- https://www.courtlistener.com/opinion/2094308/boner-v-peabody-coal-co/

### Second check: not required


## FNC-0415: Boner v. Peabody Coal Co., 142 Ill. 2d 523, 568 N.E.2d 883 (1991)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 142 Ill.2d at 539; pincite: 539.

Cited for: Boner, in fact, did consider court data in arriving at its conclusion that court congestion did not necessitate transferring the action at issue to Gallatin County. Boner,

Quotes: []

Context: ct, did consider court data in arriving at its conclusion that court congestion did not necessitate transferring the action at issue to Gallatin County. Boner, 142 Ill.2d at 539, 154 Ill.Dec. 662, 568 N.E.2d 883 (“Moreover, the 1989 statistics favor St. Cla

Fictional by design: False; 

### First check: VERIFIED

Boner text read on CourtListener; proposition located. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Boner, 142 Ill. 2d at 539: 'Moreover, the 1989 statistics favor St. Clair County rather than Gallatin County.'

- https://www.courtlistener.com/opinion/2094308/boner-v-peabody-coal-co/

### Second check: not required


## FNC-0416: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 181; pincite: 181.

Cited for: Thus, while “[t]he court congestion factor, by itself, is relatively insignificant” (Dawdy,

Quotes: []

Context: 89 statistics favor St. Clair County rather than Gallatin County”). Thus, while “[t]he court congestion factor, by itself, is relatively insignificant” (Dawdy, 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687), and is not alone sufficient to justify trans

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 181 (CourtListener 9819104): 'The court congestion factor, by itself, is relatively insignificant ... there were 1,867 jury actions for damages in excess of $50,000 pending in Madison County, while only 137 ... "crowded to the point where congestion is of great concern."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0417: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 181; pincite: 181.

Cited for: 92, 797 N.E.2d 687), and is not alone sufficient to justify transfer (Dawdy,

Quotes: []

Context: r, by itself, is relatively insignificant” (Dawdy, 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687), and is not alone sufficient to justify transfer (Dawdy, 207 Ill.2d at 181, 278 Ill.Dec. 92, 797 N.E.2d 687), in this case, this factor does weigh in favo

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 181 (CourtListener 9819104): 'The court congestion factor, by itself, is relatively insignificant ... there were 1,867 jury actions for damages in excess of $50,000 pending in Madison County, while only 137 ... "crowded to the point where congestion is of great concern."'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0418: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 512; pincite: 512.

Cited for: The lawsuit at issue in Guerine arose from a car accident involving the individual defendant and the decedent. Guerine,

Quotes: []

Context: tly to govern the outcome of this case. The lawsuit at issue in Guerine arose from a car accident involving the individual defendant and the decedent. Guerine, 198 Ill.2d at 512, 261 Ill.Dec. 763, 764 N.E.2d 54. A boat trailer broke away from the individual

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 512 (CourtListener 3134965): 'The trailer broke away from Guerine's vehicle, crossed the road into oncoming traffic, and struck head-on a Hyundai Accent driven by Angel Malone of Batavia, Kane County.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0419: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 512; pincite: 512.

Cited for: A boat trailer broke away from the individual defendant's vehicle, crossed into oncoming traffic, and struck the decedent's vehicle, killing her. Guerine,

Quotes: []

Context: 54. A boat trailer broke away from the individual defendant's vehicle, crossed into oncoming traffic, and struck the decedent's vehicle, killing her. Guerine, 198 Ill.2d at 512, 261 Ill.Dec. 763, 764 N.E.2d 54. The plaintiff bank, as the executor of the de

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 512 (CourtListener 3134965): 'The trailer broke away from Guerine's vehicle, crossed the road into oncoming traffic, and struck head-on a Hyundai Accent driven by Angel Malone of Batavia, Kane County.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0420: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 513; pincite: 513.

Cited for: or of the decedent's estate, and the decedent's two minor sons, by their father, the decedent's husband, filed suit in Cook County against the individual defendant for negligence and against the manufacturer of the boat trailer for product liability. Guerine,

Quotes: []

Context: and, filed suit in Cook County against the individual defendant for negligence and against the manufacturer of the boat trailer for product liability. Guerine, 198 Ill.2d at 513, 261 Ill.Dec. 763, 764 N.E.2d 54. The individual defendant resided in Cook Coun

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 513 (CourtListener 3134965): 'filed a nine-count wrongful-death complaint in the Cook County circuit court against Guerine for negligent operation of his vehicle, and J.Q. Tex for defective design and manufacture of the boat trailer.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0421: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 512-13; pincite: 512-13.

Cited for: The individual defendant resided in Cook County, the corporate defendant was headquartered in Mishawaka, Indiana, and the accident had occurred in De Kalb County. Guerine,

Quotes: []

Context: al defendant resided in Cook County, the corporate defendant was headquartered in Mishawaka, Indiana, and the accident had occurred in De Kalb County. Guerine, 198 Ill.2d at 512-13, 524, 261 Ill.Dec. 763, 764 N.E.2d 54. The circuit court allowed the corporate

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 512-13 (CourtListener 3134965): 'Richard Guerine of Melrose Park, Cook County ... a trailer manufactured by J.Q. Tex, Inc. (J.Q. Tex), a Mishawaka, Indiana, corporation.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0422: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 513-14; pincite: 513-14.

Cited for: The circuit court allowed the corporate defendant's motion to transfer the action out of Cook County, and the appellate court denied the plaintiffs leave to appeal. Guerine,

Quotes: []

Context: urt allowed the corporate defendant's motion to transfer the action out of Cook County, and the appellate court denied the plaintiffs leave to appeal. Guerine, 198 Ill.2d at 513-14, 261 Ill.Dec. 763, 764 N.E.2d 54. In reversing the judgment of the circuit cour

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 513-14 (CourtListener 3134965): 'The trial court granted this motion ... The appellate court denied the plaintiffs' petition for leave to appeal'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0423: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 526; pincite: 526.

Cited for:  intrastate forum non conveniens motion to transfer venue where * * * the potential trial witnesses are scattered among several counties, including the plaintiff's chosen forum, and no single county enjoys a predominant connection to the litigation.” Guerine,

Quotes: []

Context: are scattered among several counties, including the plaintiff's chosen forum, and no single county enjoys a predominant connection to the litigation.” Guerine, 198 Ill.2d at 526, 261 Ill.Dec. 763, 764 N.E.2d 54. The potential witnesses were “scattered among

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 526 (CourtListener 3134965): 'a trial court abuses its discretion in granting an intrastate forum non conveniens motion to transfer venue where, as here, the potential trial witnesses are scattered among several counties, including the plaintiffs chosen forum, and no single county enjoys a predominant connection to the litigation.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0424: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 524; pincite: 524.

Cited for: The potential witnesses were “scattered among several counties” because they resided in Cook County, De Kalb County, Du Page County, Kane County, and Winnebago County. See Guerine,

Quotes: []

Context: es were “scattered among several counties” because they resided in Cook County, De Kalb County, Du Page County, Kane County, and Winnebago County. See Guerine, 198 Ill.2d at 524- 25, 261 Ill.Dec. 763, 764 N.E.2d 54. There were various reasons why no single

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 524 (CourtListener 3134965): 'On the defense side, Guerine lives in Cook County and never filed a forum non conveniens motion. ... Cook County is a more convenient forum for all parties, especially the defendants.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0425: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 524-25; pincite: 524-25.

Cited for: There were various reasons why no single county enjoyed “a predominant connection to the litigation,” as reflected in our analysis of the relevant private and public interest factors. See Guerine,

Quotes: []

Context: gle county enjoyed “a predominant connection to the litigation,” as reflected in our analysis of the relevant private and public interest factors. See Guerine, 198 Ill.2d at 524-25, 261 Ill.Dec. 763, 764 N.E.2d 54. While the accident occurred in De Kalb County

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 524-25 (CourtListener 3134965): 'Guerine's passenger McKinney lives in Cook County. Guerine's other passenger Tischer lives in Du Page County ... Dr. Blum ... comes from Winnebago County.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0426: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 525; pincite: 525.

Cited for: While the accident occurred in De Kalb County, and thus gave the plaintiffs' negligence claim against the individual defendant a “local flavor,” the plaintiffs' product liability claim against the corporate defendant was “less localized.” Guerine,

Quotes: []

Context: claim against the individual defendant a “local flavor,” the plaintiffs' product liability claim against the corporate defendant was “less localized.” Guerine, 198 Ill.2d at 525, 261 Ill.Dec. 763, 764 N.E.2d 54. Moreover, despite the accident's occurrence i

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 525 (CourtListener 3134965): 'the plaintiffs' negligence claim against Guerine has a local flavor. The plaintiffs' products liability claim against J.Q. Tex, however, is less localized. ... We live in a smaller world'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0427: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 18 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 524; pincite: 524.

Cited for: Moreover, despite the accident's occurrence in De Kalb County, Cook County clearly was more accessible to the parties. Guerine,

Quotes: []

Context: 61 Ill.Dec. 763, 764 N.E.2d 54. Moreover, despite the accident's occurrence in De Kalb County, Cook County clearly was more accessible to the parties. Guerine, 198 Ill.2d at 524, 261 Ill.Dec. 763, 764 N.E.2d 54. The individual defendant resided there and ne

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 524 (CourtListener 3134965): 'On the defense side, Guerine lives in Cook County and never filed a forum non conveniens motion. ... Cook County is a more convenient forum for all parties, especially the defendants.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0428: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 524; pincite: 524.

Cited for:  venues. Guerine,

Quotes: []

Context: venues. Guerine, 198 Ill.2d at 524, 261 Ill.Dec. 763, 764 N.E.2d 54. In addition, as we recognized in our holding,

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 524 (CourtListener 3134965): 'On the defense side, Guerine lives in Cook County and never filed a forum non conveniens motion. ... Cook County is a more convenient forum for all parties, especially the defendants.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0429: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 524-25; pincite: 524-25.

Cited for: In addition, as we recognized in our holding, the potential witnesses were disbursed among several counties, including the county where the plaintiffs filed suit. Guerine,

Quotes: []

Context: as we recognized in our holding, the potential witnesses were disbursed among several counties, including the county where the plaintiffs filed suit. Guerine, 198 Ill.2d at 524-25, 261 Ill.Dec. 763, 764 N.E.2d 54. We distinguished Guerine in Dawdy. There we o

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 524-25 (CourtListener 3134965): 'Guerine's passenger McKinney lives in Cook County. Guerine's other passenger Tischer lives in Du Page County ... Dr. Blum ... comes from Winnebago County.'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0430: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 184; pincite: 184.

Cited for: There we observed that, unlike in Guerine, none of the witnesses resided in the county where suit was filed, and the transferee county had a predominant connection to the litigation. Dawdy,

Quotes: []

Context: in Guerine, none of the witnesses resided in the county where suit was filed, and the transferee county had a predominant connection to the litigation. Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687 (“In this case, however, none of the witnesses

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 184 (CourtListener 9819104): 'In this case, however, none of the witnesses reside in Madison County and Macoupin County has a predominant connection to this case. ... the balance of factors strongly favors transfer to Macoupin County.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0431: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 178; pincite: 178.

Cited for: It is significant that, in addition to the fact that none of the potential witnesses resided in the county where suit was filed, on the whole they resided closer to the transferee county. Dawdy,

Quotes: []

Context: to the fact that none of the potential witnesses resided in the county where suit was filed, on the whole they resided closer to the transferee county. Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. Furthermore, while we did not explicitly elab

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 178 (CourtListener 9819104): 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County. ... This convenience factor is not concerned with the necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0432: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 170; pincite: 170.

Cited for: Unlike the individual defendant in Guerine, the individual defendant in Dawdy was a resident of the transferee county. See Dawdy,

Quotes: []

Context: and public interest factors. Unlike the individual defendant in Guerine, the individual defendant in Dawdy was a resident of the transferee county. See Dawdy, 207 Ill.2d at 170, 183, 278 Ill.Dec. 92, 797 N.E.2d 687. In addition, unlike the mixed negligence

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 170 (CourtListener 9819104): 'Union Pacific is a Delaware corporation with its principal place of business in Omaha, Nebraska. ... Of the 18 witnesses who may be called to testify at trial, most of them reside in or near Macoupin County'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0433: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 169; pincite: 169.

Cited for: In addition, unlike the mixed negligence-product liability action in Guerine, all of the plaintiff's negligence claims in Dawdy related to the specific accident at issue, which occurred in the transferee county. See Dawdy,

Quotes: []

Context: on in Guerine, all of the plaintiff's negligence claims in Dawdy related to the specific accident at issue, which occurred in the transferee county. See Dawdy, 207 Ill.2d at 169, 183, 278 Ill.Dec. 92, 797 N.E.2d 687. Moreover, the potential witnesses in Daw

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 169 (CourtListener 9819104): 'Plaintiff sought damages for injuries sustained in a motor vehicle accident that occurred in Macoupin County.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0434: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 178; pincite: 178.

Cited for: Moreover, the potential witnesses in Dawdy were more closely linked to the transferee county than in Guerine. See Dawdy,

Quotes: []

Context: 183, 278 Ill.Dec. 92, 797 N.E.2d 687. Moreover, the potential witnesses in Dawdy were more closely linked to the transferee county than in Guerine. See Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. The grounds on which the majority distinguish

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 178 (CourtListener 9819104): 'these factors slightly weigh in favor of the convenience of Macoupin County over Madison County. ... This convenience factor is not concerned with the necessity of viewing the site of the injury, but rather is concerned with the possibility of viewing the site, if appropriate.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0435: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 453; pincite: 453.

Cited for: First, the majority asserts that “in Dawdy, none of the witnesses resided in the plaintiff's chosen forum.”

Quotes: []

Context: ase are unpersuasive and likely to cause confusion. First, the majority asserts that “in Dawdy, none of the witnesses resided in the plaintiff's chosen forum.” 219 Ill.2d at 453, 302 Ill.Dec. at 376, 848 N.E.2d at 940. It is true that, in this case, two pot

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 453: 'First, in Dawdy, none of the witnesses resided in the plaintiffs chosen forum. Second, in Dawdy, the possibility of a jury view of the accident scene was a practical consideration.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0436: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 453; pincite: 453.

Cited for: Second, the majority states that “in Dawdy, the possibility of a jury view of the accident scene was a practical consideration.”

Quotes: []

Context: e county where suit was filed. Second, the majority states that “in Dawdy, the possibility of a jury view of the accident scene was a practical consideration.” 219 Ill.2d at 453, 302 Ill.Dec. at 376, 848 N.E.2d at 940. As discussed, the possibility of a jur

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 453: 'First, in Dawdy, none of the witnesses resided in the plaintiffs chosen forum. Second, in Dawdy, the possibility of a jury view of the accident scene was a practical consideration.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0437: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 453; pincite: 453.

Cited for: Third, the majority notes that “in Dawdy, the defendant railroad was attempting to transfer the cause to the defendant employee's county of residence.”

Quotes: []

Context: s case. Third, the majority notes that “in Dawdy, the defendant railroad was attempting to transfer the cause to the defendant employee's county of residence.” 219 Ill.2d at 453, 302 Ill.Dec. at 376, 848 N.E.2d at 940. As with the majority's statement regar

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 453: 'First, in Dawdy, none of the witnesses resided in the plaintiffs chosen forum. Second, in Dawdy, the possibility of a jury view of the accident scene was a practical consideration.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0438: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 448; pincite: 448.

Cited for: es, the majority does not engage in a separate analysis of this factor, other than to state the obvious proposition that a defendant cannot prevail on a motion to transfer by simply asserting that the plaintiff's chosen venue is inconvenient to the plaintiff (

Quotes: []

Context: ous proposition that a defendant cannot prevail on a motion to transfer by simply asserting that the plaintiff's chosen venue is inconvenient to the plaintiff (219 Ill.2d at 448, 302 Ill.Dec. at 373-74, 848 N.E.2d at 937-38), and to conclude that defendants

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 448: 'defendants cannot assert that the plaintiff's chosen forum is inconvenient to the plaintiff.'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0439: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430, 848 N.E.2d 927 (2006)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 19 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 219 Ill.2d at 450; pincite: 450.

Cited for: at 373-74, 848 N.E.2d at 937-38), and to conclude that defendants failed to show they would be inconvenienced by a trial in St. Clair County (

Quotes: []

Context: 448, 302 Ill.Dec. at 373-74, 848 N.E.2d at 937-38), and to conclude that defendants failed to show they would be inconvenienced by a trial in St. Clair County (219 Ill.2d at 450, 302 Ill.Dec. at 373-74, 848 N.E.2d

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference to the Langenhorst opinion itself (219 Ill. 2d 430); referenced passage located in the official text read on CourtListener (lead opinion page markers offset 10).

Excerpt read: Langenhorst, 219 Ill. 2d at 450: 'We discern no inconvenience for the defendants to try this case in St. Clair County when Clinton and St. Clair Counties are adjacent'

- https://www.courtlistener.com/opinion/9819147/langenhorst-v-norfolk-southern-railway-company/
- https://www.courtlistener.com/opinion/9819148/langenhorst-v-norfolk-southern-railway-company/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-0440: First American Bank v. Guerine, 198 Ill. 2d 511, 764 N.E.2d 54 (2002) (West caption: First National Bank v. Guerine)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 20 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 198 Ill.2d at 517; pincite: 517.

Cited for: Clair County as a venue for her lawsuit is entitled to less deference than would otherwise be appropriate. See Guerine,

Quotes: []

Context: As a result, plaintiff's choice of St. Clair County as a venue for her lawsuit is entitled to less deference than would otherwise be appropriate. See Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54; Dawdy, 207 Ill.2d at 173-74, 278 Ill.Dec. 92,

Fictional by design: False; 

### First check: VERIFIED

Guerine read on CourtListener (Illinois Reports text with page markers) and in the supplied attachment; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Guerine, 198 Ill. 2d at 517 (CourtListener 3134965): 'Court congestion is a relatively insignificant factor, especially where the record does not show the other forum would resolve the case more quickly. ... The plaintiff has a substantial interest in choosing the forum where his rights will be vindicated'

- https://www.courtlistener.com/opinion/3134965/first-national-bank-v-guerine/
- https://www.courtlistener.com/opinion/2056494/first-nat-bank-v-guerine/
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-0441: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167, 797 N.E.2d 687 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: Langenhorst v. Norfolk Southern.pdf, PDF page 20 (Garman, J., dissenting; the attachment has no dissent heading).

Authority type: case; as written: 207 Ill.2d at 173-74; pincite: 173-74.

Cited for: See Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54; Dawdy,

Quotes: []

Context: enue for her lawsuit is entitled to less deference than would otherwise be appropriate. See Guerine, 198 Ill.2d at 517, 261 Ill.Dec. 763, 764 N.E.2d 54; Dawdy, 207 Ill.2d at 173-74, 278 Ill.Dec. 92, 797 N.E.2d 687. On balance, the private interest factors weig

Fictional by design: False; 

### First check: VERIFIED

Dawdy majority opinion read in full on CourtListener; proposition located at the cited page. Pin checked by mapping the Illinois Reports page markers in the CourtListener (Harvard CAP) text read in this session.

Excerpt read: Dawdy, 207 Ill. 2d at 173-74 (CourtListener 9819104): 'When the plaintiff is foreign, however, this assumption is much less reasonable. ... a foreign plaintiffs choice deserves less deference.'

- https://www.courtlistener.com/opinion/3135004/dawdy-jr-v-union-pacific-rr-co/

### Second check: not required


## FNC-0442: Ill. S. Ct. R. 306(a)(4) (1990 numbering)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 1.

Authority type: court_rule; as written: Supreme Court Rule 306(a)(4); pincite: .

Cited for: St. Mary's Hospital's petition for interlocutory appeal

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Bradbury’s own judicial text says St. Mary’s petitioned under Rule 306(a)(4) following its February 1994 venue ruling, and later judicial text/current official Rule 306(a)(4) cover residence-based transfer. The signed 1993 amendment or authenticated February 1994 compilation was not obtained, so exact historical rule text at the petition date remains unverified.

Excerpt read: Bradbury reports St. Mary’s filed under Rule 306(a)(4). Current official Rule 306(a)(4) covers defendant-residence venue transfer; exact February 1994 rule text not read.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf
- https://www.illinoiscourts.gov/resources/e1bf857c-ae6d-446c-b5d3-e01583b83878/093020.pdf
- https://law.counselstack.com/opinion/ferguson-v-bill-berger-associates-inc-illappct-1998

### Second check: not required


## FNC-0443: 735 ILCS 5/2-101 (venue)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: statute; as written: section 2-101; pincite: .

Cited for: Venue proper where part of the transaction occurred, including place of death

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Short-form reference to 735 ILCS 5/2-101 (quoted at p.1); text matches.

Excerpt read: 'every action must be commenced (1) in the county of residence of any defendant who is joined in good faith ... or (2) in the county in which the transaction or some part thereof occurred out of which the cause of action arose.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073500050K2-101.htm

### Second check: not required


## FNC-0444: 735 ILCS 5/2-104 (wrong venue; motion to transfer)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: Bradbury v. St. Mary's Hospital.pdf, PDF page 2.

Authority type: statute; as written: section 2-104 of the Code; pincite: .

Cited for: Defendants' improper-venue motions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current ILGA text read; the cited 1992 West edition was not read, but the provision's subject (transfer for improper venue) is unchanged in substance.

Excerpt read: 'No action shall abate or be dismissed because commenced in the wrong venue if there is a proper venue to which the cause may be transferred.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073500050K2-104.htm

### Second check: not required


## FNC-0445: Ill. S. Ct. R. 306(a)(2)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: First Am Bank v. Guerine.pdf, PDF page 5.

Authority type: court_rule; as written: Rule 306(a)(2) petitions; pincite: .

Cited for: Appellate court decisions on FNC petitions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage.

Excerpt read: '(2) from an order of the circuit court allowing or denying a motion to dismiss on the grounds of forum non conveniens, or ... a motion to transfer a case to another county within this State on such grounds'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0446: Ill. S. Ct. R. 315, 317

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 4 (printed page 4), table of contents.

Authority type: court_rule; as written: Rules 315/317; pincite: .

Cited for: Supreme Court Table 2 title (petitions for leave to appeal / appeals as of right)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rules 315 and 317 exist with those subjects.

Excerpt read: 'Rule 315. Leave to Appeal From the Appellate Court to the Supreme Court'; 'Rule 317. Appeals from the Appellate Court to the Supreme Court as of Right'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0447: Ill. S. Ct. R. 23

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 4 (printed page 4), table of contents entry "Opinion or Rule 23 Order".

Authority type: court_rule; as written: Rule 23; pincite: .

Cited for: Appellate dispositions by Rule 23 order

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 23. Disposition of Cases in the Appellate Court ... (b) Written Order.'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0448: Ill. S. Ct. R. 23

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 4 (printed page 4), table of contents entry "Opinions and Rule 23 Orders".

Authority type: court_rule; as written: Rule 23; pincite: .

Cited for: Appellate dispositions by Rule 23 order

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 23. Disposition of Cases in the Appellate Court ... (b) Written Order.'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0449: Ill. S. Ct. R. 86-95 (mandatory arbitration)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 8 (printed page 8), case category AR.

Authority type: court_rule; as written: Supreme Court Rules 86 through 95; pincite: .

Cited for: Mandatory arbitration case category

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage.

Excerpt read: 'Rule 86. Actions Subject to Mandatory Arbitration' ... 'Rule 95. Form of Notice of Rejection of Award'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0450: Probate Act of 1975, 755 ILCS 5

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 8 (printed page 8), case category GR.

Authority type: statute; as written: Probate Act of 1975, as amended; pincite: .

Cited for: Guardianship case category

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 'This Act may be cited as the Probate Act of 1975.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/075500050K1-1.htm

### Second check: not required


## FNC-0451: Ill. S. Ct. R. 222

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 8 (printed page 8), case category L/LA.

Authority type: court_rule; as written: Supreme Court Rule 222; pincite: .

Cited for: Damages pleaded under Rule 222 determine Law category (> $50,000)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 222(b) requires the damages affidavit stating whether damages exceed $50,000, which matches the report's use.

Excerpt read: '(b) Affidavit re Damages Sought. Any civil action seeking money damages shall have attached to the initial pleading the party's affidavit that the total of money damages sought does or does not exceed $50,000.'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0452: Ill. S. Ct. R. 222

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 9 (printed page 9), case category LM.

Authority type: court_rule; as written: Supreme Court Rule 222; pincite: .

Cited for: Damages pleaded under Rule 222 determine Law Magistrate category (<= $50,000)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule 222(b) damages affidavit.

Excerpt read: '(b) Affidavit re Damages Sought. Any civil action seeking money damages shall have attached to the initial pleading the party's affidavit that the total of money damages sought does or does not exceed $50,000.'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0453: Ill. S. Ct. R. 281

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 9 (printed page 9), case category SC.

Authority type: court_rule; as written: "...a civil action based on either tort or contract for money not in excess of $10,000, exclusive of interest and costs" (Supreme Court Rule 281); pincite: .

Cited for: Small-claim definition (quoted)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Quotation matches current Rule 281 verbatim.

Excerpt read: 'a small claim is a civil action based on either tort or contract for money not in excess of $10,000, exclusive of interest and costs.'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0454: Adoption Act, 750 ILCS 50/0.01 et seq.

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 10 (printed page 10), case category AD.

Authority type: statute; as written: 750 ILCS 50/0.01 et seq.; pincite: .

Cited for: Adoption case category

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 'This Act may be cited as the Adoption Act.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/075000500K0.01.htm

### Second check: not required


## FNC-0455: 750 ILCS 5/303

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 10 (printed page 10), case category DC.

Authority type: statute; as written: 750 ILCS 5/303; pincite: .

Cited for: Dissolution, civil union, annulment, legal separation or separate maintenance "as defined in" this section

Quotes: []

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

750 ILCS 5/303 is 'Legitimacy of Children' (children of an invalid marriage are lawful); it does not define dissolution, annulment, legal separation or maintenance proceedings (those are in Parts III-V, e.g. 5/301, 5/401, 5/402). The report cites a real section for definitions it does not contain.

Excerpt read: 'Sec. 303. Legitimacy of Children.) Children born or adopted of a marriage declared invalid are the lawful children of the parties.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/075000050K303.htm

### Second check: MISCHARACTERIZED

The Annual Report DC definition says dissolution and related proceedings are 'as defined in 750 ILCS 5/303.' The full official Illinois General Assembly text of section 303 concerns children's legal status after an invalid marriage or parents' later marriage. It defines none of the listed proceeding types. The cite is to a real but inapposite section, apparently an error in the background report rather than the litigation rubric.

Excerpt read: Official ILGA section 303 full text: heading 'Legitimacy of Children' and two sentences on children of an invalid marriage or parents who later marry; Annual Report PDF p.10 uses it for DC cases.

- https://www.ilga.gov/ftp/ILCS/Ch%200750/Act%200005/075000050K303.html
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0456: 750 ILCS 5/303

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 10 (printed page 10), case category DN.

Authority type: statute; as written: 750 ILCS 5/303; pincite: .

Cited for: Dissolution, civil union, annulment, legal separation or separate maintenance "as defined in" this section

Quotes: []

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

750 ILCS 5/303 is 'Legitimacy of Children' (children of an invalid marriage are lawful); it does not define dissolution, annulment, legal separation or maintenance proceedings (those are in Parts III-V, e.g. 5/301, 5/401, 5/402). The report cites a real section for definitions it does not contain.

Excerpt read: 'Sec. 303. Legitimacy of Children.) Children born or adopted of a marriage declared invalid are the lawful children of the parties.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/075000050K303.htm

### Second check: MISCHARACTERIZED

The Annual Report DN definition repeats the same 750 ILCS 5/303 citation for dissolution and related proceedings without minor children. Official section 303 is about the lawful status of children, not definitions of dissolution, annulment, legal separation or maintenance. This repeats an error in a background source, not a scored rubric criterion.

Excerpt read: Official ILGA section 303 full text: 'Legitimacy of Children' heading and lawful-child status; Annual Report PDF p.10 cites it for DN cases.

- https://www.ilga.gov/ftp/ILCS/Ch%200750/Act%200005/075000050K303.html
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

Model: gpt-6-sol; reasoning effort: high.

## FNC-0457: Unified Code of Corrections, 730 ILCS 5/5-1 et seq.

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 11 (printed page 11), case category CF.

Authority type: statute; as written: Unified Code of Corrections (730 ILCS 5/5-1 et seq.); pincite: .

Cited for: Felony / misdemeanor / petty and business offense definitions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter V of the Unified Code defines felony (5-1-9), misdemeanor (5-1-14), petty offense (5-1-17) and business offense (5-1-2); class A-C misdemeanor sentencing provisions were not separately read.

Excerpt read: 5-1-9: '"Felony" means an offense for which a sentence to a term of imprisonment in a penitentiary for one year or more is provided.'; 5-1-14 (misdemeanor); 5-1-17 (petty offense); 5-1-2 (business offense)

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-9.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-14.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-17.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-2.htm

### Second check: not required


## FNC-0458: Unified Code of Corrections, 730 ILCS 5/5-1 et seq.

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 11 (printed page 11), case category CM.

Authority type: statute; as written: Unified Code of Corrections (730 ILCS 5/5-1 et seq.); pincite: .

Cited for: Felony / misdemeanor / petty and business offense definitions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter V of the Unified Code defines felony (5-1-9), misdemeanor (5-1-14), petty offense (5-1-17) and business offense (5-1-2); class A-C misdemeanor sentencing provisions were not separately read.

Excerpt read: 5-1-9: '"Felony" means an offense for which a sentence to a term of imprisonment in a penitentiary for one year or more is provided.'; 5-1-14 (misdemeanor); 5-1-17 (petty offense); 5-1-2 (business offense)

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-9.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-14.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-17.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-2.htm

### Second check: not required


## FNC-0459: Unified Code of Corrections, 730 ILCS 5/5-1 et seq.

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 11 (printed page 11), case category QC.

Authority type: statute; as written: Unified Code of Corrections (730 ILCS 5/5-1 et seq.); pincite: .

Cited for: Felony / misdemeanor / petty and business offense definitions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Chapter V of the Unified Code defines felony (5-1-9), misdemeanor (5-1-14), petty offense (5-1-17) and business offense (5-1-2); class A-C misdemeanor sentencing provisions were not separately read.

Excerpt read: 5-1-9: '"Felony" means an offense for which a sentence to a term of imprisonment in a penitentiary for one year or more is provided.'; 5-1-14 (misdemeanor); 5-1-17 (petty offense); 5-1-2 (business offense)

- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-9.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-14.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-17.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/073000050K5-1-2.htm

### Second check: not required


## FNC-0460: Illinois Vehicle Code § 11-501 (625 ILCS 5/11-501)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 11 (printed page 11), case category DT.

Authority type: statute; as written: Section 11-501 of the Illinois Vehicle Code; pincite: .

Cited for: DUI case category

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 'Driving while under the influence of alcohol, other drug or drugs, intoxicating compound or compounds or any combination thereof.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/062500050K11-501.htm

### Second check: not required


## FNC-0461: Snowmobile Registration and Safety Act § 5-7 (625 ILCS 40/5-7)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 11 (printed page 11), case category DT.

Authority type: statute; as written: Section 5-7 of the Snowmobile Registration and Safety Act; pincite: .

Cited for: DUI case category

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 'Operating a snowmobile while under the influence of alcohol or other drug or drugs ...'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/062500400K5-7.htm

### Second check: not required


## FNC-0462: Boat Registration and Safety Act § 5-16 (625 ILCS 45/5-16)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 11 (printed page 11), case category DT.

Authority type: statute; as written: Section 5-16 of the Boat Registration and Safety Act; pincite: .

Cited for: DUI case category

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 'Operating a watercraft under the influence of alcohol, other drug or drugs ...'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/062500450K5-16.htm

### Second check: not required


## FNC-0463: Ill. S. Ct. R. 501(c), (f)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 11 (printed page 11), case category CV.

Authority type: court_rule; as written: Supreme Court Rule 501(c); pincite: .

Cited for: Conservation offense definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage.

Excerpt read: '(c) Conservation Offense ...'; '(f) Traffic Offense ... (i) "Major Traffic Offense" ... (ii) "Minor Traffic Offense" means a petty offense or business offense ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0464: Criminal Code § 12-3.2, domestic battery (720 ILCS 5/12-3.2)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 11 (printed page 11), case category DV.

Authority type: statute; as written: Section 12-3.2 of the Criminal Code (720 ILCS 5/12-3.2); pincite: .

Cited for: Domestic battery case category

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 'Sec. 12-3.2. Domestic battery. (a) A person commits domestic battery if he or she knowingly without legal justification ...'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/072000050K12-3.2.htm

### Second check: not required


## FNC-0465: Ill. S. Ct. R. 501(c), (f)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 11 (printed page 11), case category MT.

Authority type: court_rule; as written: Supreme Court Rule 501(f)(1)(i); pincite: .

Cited for: Major traffic offense definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage.

Excerpt read: '(c) Conservation Offense ...'; '(f) Traffic Offense ... (i) "Major Traffic Offense" ... (ii) "Minor Traffic Offense" means a petty offense or business offense ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0466: Ill. S. Ct. R. 501(c), (f)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 11 (printed page 11), case category OV.

Authority type: court_rule; as written: Supreme Court Rule 501(f); pincite: .

Cited for: Traffic ordinance violations definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage.

Excerpt read: '(c) Conservation Offense ...'; '(f) Traffic Offense ... (i) "Major Traffic Offense" ... (ii) "Minor Traffic Offense" means a petty offense or business offense ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0467: Ill. S. Ct. R. 501(c), (f)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 11 (printed page 11), case category TR.

Authority type: court_rule; as written: Supreme Court Rule 501(f)(1)(ii); pincite: .

Cited for: Minor traffic offense definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage.

Excerpt read: '(c) Conservation Offense ...'; '(f) Traffic Offense ... (i) "Major Traffic Offense" ... (ii) "Minor Traffic Offense" means a petty offense or business offense ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0468: Ill. S. Ct. R. 585

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 12 (printed page 12), case category CL.

Authority type: court_rule; as written: Supreme Court Rule 585; pincite: .

Cited for: Civil law violation case category

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) read; subject matches the citing passage.

Excerpt read: 'Rules 585 through 590 are applicable to civil law violations, pursuant to section 4(a) of the Cannabis Control Act'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0469: Juvenile Court Act of 1987, 705 ILCS 405

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 12 (printed page 12), case category J/JV.

Authority type: statute; as written: 705 ILCS 405/3-1 est seq. of the Juvenile Court Act of 1987; pincite: .

Cited for: Minors requiring authoritative intervention

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

705 ILCS 405/3-1 governs minors requiring authoritative intervention ('est seq.' is a typo for 'et seq.').

Excerpt read: 705 ILCS 405/3-1: 'Proceedings may be instituted under this Article concerning minors who require authoritative intervention as defined in Section 3-3 ...'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K1-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K3-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K4-3.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K5-101.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-31.htm

### Second check: not required


## FNC-0470: Juvenile Court Act of 1987, 705 ILCS 405

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 12 (printed page 12), case category J/JV.

Authority type: statute; as written: 705 ILCS 405/1-1 et seq. of the Juvenile Court Act of 1987; pincite: .

Cited for: Other Juvenile Court Act proceedings

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 1-1: 'This Act shall be known and may be cited as the Juvenile Court Act of 1987.'; 2-1, 3-1, 4-3, 5-101, 2-31 read

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K1-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K3-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K4-3.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K5-101.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-31.htm

### Second check: not required


## FNC-0471: Juvenile Court Act of 1987, 705 ILCS 405

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 12 (printed page 12), case category JA.

Authority type: statute; as written: 705 ILCS 405/2-1, et seq. of the Juvenile Court Act of 1987; pincite: .

Cited for: Abused, neglected or dependent minors

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 705 ILCS 405/2-1: 'Proceedings may be instituted under the provisions of this Article concerning minors who are abused, neglected or dependent'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K1-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K3-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K4-3.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K5-101.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-31.htm

### Second check: not required


## FNC-0472: Juvenile Court Act of 1987, 705 ILCS 405

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 12 (printed page 12), case category JD.

Authority type: statute; as written: Substance Use Disorder Act (705 ILCS 405/4-1 et seq.); pincite: .

Cited for: Addicted minors

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

705 ILCS 405/4-1 et seq. is Article IV (addicted minors) of the Juvenile Court Act, not the Substance Use Disorder Act; section 4-3 defines an addicted minor by reference to the Substance Use Disorder Act. Name and citation are conflated, but the category is correctly located.

Excerpt read: 705 ILCS 405/4-3: 'Those who are addicted include any minor who has a substance use disorder as defined in the Substance Use Disorder Act.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K1-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K3-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K4-3.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K5-101.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-31.htm

### Second check: not required


## FNC-0473: Juvenile Court Act of 1987, 705 ILCS 405

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 12 (printed page 12), case category JD.

Authority type: statute; as written: Juvenile Court Act of 1987 (705 ILCS 405/5-101 et seq.); pincite: .

Cited for: Delinquent minors

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 1-1: 'This Act shall be known and may be cited as the Juvenile Court Act of 1987.'; 2-1, 3-1, 4-3, 5-101, 2-31 read

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K1-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K3-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K4-3.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K5-101.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-31.htm

### Second check: not required


## FNC-0474: Juvenile Court Act of 1987, 705 ILCS 405

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 28 (printed page 28), definition of "Closed" for juvenile cases.

Authority type: statute; as written: Juvenile Court Act of 1987 (705 ILCS 405/Article 2); pincite: .

Cited for: Age at which juvenile (Article II) cases close

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Article II proceedings terminate automatically at age 21 (705 ILCS 405/2-31).

Excerpt read: 705 ILCS 405/2-31(1): 'All proceedings under Article II of this Act in respect of any minor automatically terminate upon the minor attaining the age of 21 years.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K1-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K3-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K4-3.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K5-101.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-31.htm

### Second check: not required


## FNC-0475: Clerks of Courts Act, 705 ILCS 105

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 165 (printed page 165), table footnote.

Authority type: statute; as written: Clerks of Courts Act; pincite: .

Cited for: Clerk fee categories in revenue tables

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 'This Act may be cited as the Clerks of Courts Act.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070501050K0.01.htm

### Second check: not required


## FNC-0476: Clerks of Courts Act, 705 ILCS 105

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 166 (printed page 166), table footnote.

Authority type: statute; as written: Clerks of Courts Act; pincite: .

Cited for: Clerk fee categories in revenue tables

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 'This Act may be cited as the Clerks of Courts Act.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070501050K0.01.htm

### Second check: not required


## FNC-0477: Clerks of Courts Act, 705 ILCS 105

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 167 (printed page 167), table footnote.

Authority type: statute; as written: Clerks of Courts Act; pincite: .

Cited for: Clerk fee categories in revenue tables

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Current official ILGA text read in this session.

Excerpt read: 'This Act may be cited as the Clerks of Courts Act.'

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070501050K0.01.htm

### Second check: not required


## FNC-0478: Walker v. Chasteen, 2021 IL 126086 (June 17, 2021)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 195 (printed page 195), table footnote (Foreclosure Prevention Program Fund column).

Authority type: case; as written: Walker v. Chasteen ... 6/17/2021; pincite: .

Cited for: Supreme court affirmed that the foreclosure-fee statute is unconstitutional

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Walker v. Chasteen, 2021 IL 126086, filed June 17, 2021, affirmed the circuit court's ruling that the statutes funding the Foreclosure Prevention Program Fund are facially unconstitutional under the free access clause.

Excerpt read: 'we have already determined that the statutes at issue are facially unconstitutional as violative of the free access clause.'

- https://www.courtlistener.com/opinion/5127955/walker-v-chasteen/

### Second check: not required


## FNC-0479: Walker v. Chasteen, 2021 IL 126086 (June 17, 2021)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 196 (printed page 196), table footnote (Foreclosure Prevention Program Fund column).

Authority type: case; as written: Walker v. Chasteen ... 6/17/2021; pincite: .

Cited for: Supreme court affirmed that the foreclosure-fee statute is unconstitutional

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Walker v. Chasteen, 2021 IL 126086, filed June 17, 2021, affirmed the circuit court's ruling that the statutes funding the Foreclosure Prevention Program Fund are facially unconstitutional under the free access clause.

Excerpt read: 'we have already determined that the statutes at issue are facially unconstitutional as violative of the free access clause.'

- https://www.courtlistener.com/opinion/5127955/walker-v-chasteen/

### Second check: not required


## FNC-0480: Walker v. Chasteen, 2021 IL 126086 (June 17, 2021)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 197 (printed page 197), table footnote (Foreclosure Prevention Program Fund column).

Authority type: case; as written: Walker v. Chasteen ... 6/17/2021; pincite: .

Cited for: Supreme court affirmed that the foreclosure-fee statute is unconstitutional

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Walker v. Chasteen, 2021 IL 126086, filed June 17, 2021, affirmed the circuit court's ruling that the statutes funding the Foreclosure Prevention Program Fund are facially unconstitutional under the free access clause.

Excerpt read: 'we have already determined that the statutes at issue are facially unconstitutional as violative of the free access clause.'

- https://www.courtlistener.com/opinion/5127955/walker-v-chasteen/

### Second check: not required


## FNC-0481: Walker v. Chasteen, 2021 IL 126086 (June 17, 2021)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 198 (printed page 198), table footnote (Foreclosure Prevention Program Fund column).

Authority type: case; as written: Walker v. Chasteen ... 6/17/2021; pincite: .

Cited for: Supreme court affirmed that the foreclosure-fee statute is unconstitutional

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Walker v. Chasteen, 2021 IL 126086, filed June 17, 2021, affirmed the circuit court's ruling that the statutes funding the Foreclosure Prevention Program Fund are facially unconstitutional under the free access clause.

Excerpt read: 'we have already determined that the statutes at issue are facially unconstitutional as violative of the free access clause.'

- https://www.courtlistener.com/opinion/5127955/walker-v-chasteen/

### Second check: not required


## FNC-0482: Walker v. Chasteen, 2021 IL 126086 (June 17, 2021)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 199 (printed page 199), table footnote (Foreclosure Prevention Program Fund column).

Authority type: case; as written: Walker v. Chasteen ... 6/17/2021; pincite: .

Cited for: Supreme court affirmed that the foreclosure-fee statute is unconstitutional

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Walker v. Chasteen, 2021 IL 126086, filed June 17, 2021, affirmed the circuit court's ruling that the statutes funding the Foreclosure Prevention Program Fund are facially unconstitutional under the free access clause.

Excerpt read: 'we have already determined that the statutes at issue are facially unconstitutional as violative of the free access clause.'

- https://www.courtlistener.com/opinion/5127955/walker-v-chasteen/

### Second check: not required


## FNC-0483: Walker v. Chasteen, 2021 IL 126086 (June 17, 2021)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 200 (printed page 200), table footnote (Foreclosure Prevention Program Fund column).

Authority type: case; as written: Walker v. Chasteen ... 6/17/2021; pincite: .

Cited for: Supreme court affirmed that the foreclosure-fee statute is unconstitutional

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Walker v. Chasteen, 2021 IL 126086, filed June 17, 2021, affirmed the circuit court's ruling that the statutes funding the Foreclosure Prevention Program Fund are facially unconstitutional under the free access clause.

Excerpt read: 'we have already determined that the statutes at issue are facially unconstitutional as violative of the free access clause.'

- https://www.courtlistener.com/opinion/5127955/walker-v-chasteen/

### Second check: not required


## FNC-0484: Juvenile Court Act of 1987, 705 ILCS 405

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 222 (printed page 222), column header "Expenses necessary for minor's needs under the Juvenile Act".

Authority type: statute; as written: Juvenile Act; pincite: .

Cited for: Disbursement category

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Refers by short name to the Juvenile Court Act of 1987.

Excerpt read: 1-1: 'This Act shall be known and may be cited as the Juvenile Court Act of 1987.'; 2-1, 3-1, 4-3, 5-101, 2-31 read

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K1-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K3-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K4-3.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K5-101.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-31.htm

### Second check: not required


## FNC-0485: Juvenile Court Act of 1987, 705 ILCS 405

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 223 (printed page 223), column header "Expenses necessary for minor's needs under the Juvenile Act".

Authority type: statute; as written: Juvenile Act; pincite: .

Cited for: Disbursement category

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Refers by short name to the Juvenile Court Act of 1987.

Excerpt read: 1-1: 'This Act shall be known and may be cited as the Juvenile Court Act of 1987.'; 2-1, 3-1, 4-3, 5-101, 2-31 read

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K1-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K3-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K4-3.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K5-101.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-31.htm

### Second check: not required


## FNC-0486: Juvenile Court Act of 1987, 705 ILCS 405

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 224 (printed page 224), column header "Expenses necessary for minor's needs under the Juvenile Act".

Authority type: statute; as written: Juvenile Act; pincite: .

Cited for: Disbursement category

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Refers by short name to the Juvenile Court Act of 1987.

Excerpt read: 1-1: 'This Act shall be known and may be cited as the Juvenile Court Act of 1987.'; 2-1, 3-1, 4-3, 5-101, 2-31 read

- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K1-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K3-1.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K4-3.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K5-101.htm
- https://www.ilga.gov/Documents/legislation/ilcs/documents/070504050K2-31.htm

### Second check: not required


## FNC-0487: Job Training Partnership Act (federal, Pub. L. 97-300)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 239 (printed page 239), probation program glossary.

Authority type: statute; as written: Job Training Partnership Act; pincite: .

Cited for: Program description

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read the original 1982 Job Training Partnership Act and the 1998 Workforce Investment Act repeal provision. The 2023 report glossary accurately describes what the former program provided, but uses present tense without noting the JTPA repeal effective July 1, 2000. It is a stale historical label in a 2023 program glossary.

Excerpt read: Pub. L. 97-300 §2: purpose is to prepare youth and unskilled adults for work and afford job training to economically disadvantaged people. Pub. L. 105-220 §199(b)(2), (c)(2)(B) repeals JTPA effective July 1, 2000.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf
- https://www.govinfo.gov/content/pkg/STATUTE-96/pdf/STATUTE-96-Pg1322.pdf
- https://www.govinfo.gov/content/pkg/PLAW-105publ220/html/PLAW-105publ220.htm

### Second check: VERIFIED_MINOR_DEFECT

I tried to upgrade this to VERIFIED and could not; Sol's minor-defect rating stands. Page 239 of the 2023 report is an 'ABBREVIATIONS' page explaining column headings. It defines JTPA as 'Job Training Partnership Act: Program that provides training activities to prepare income eligible persons for employment.' The JTPA column is still in use: page 273, 'Juvenile Programs Ordered, Totals for the Year 2023', has a JTPA column with nonzero entries (for example, Union County 2 and 1st Circuit total 2). The label is a legacy reporting category. Pub. L. 97-300 § 2 (96 Stat. 1322, read on govinfo) states the purpose 'to establish programs to prepare youth and unskilled adults for entry into the labor force and to afford job training to those economically disadvantaged individuals ...', so the description of what the program does is accurate. Pub. L. 105-220 § 199(b)(2) and (c)(2)(B) (read on govinfo) repeal the JTPA effective July 1, 2000. A 2023 glossary that describes the Act in the present tense as a program that 'provides' training is stale. This is a minor defect in a descriptive column label, not a mischaracterization; the report makes no legal claim that depends on it.

Excerpt read: Report p.239: 'ABBREVIATIONS / Explanations for abbreviations used in column headings in this section are explained below. ... JTPA ... Job Training Partnership Act: Program that provides training activities to prepare income eligible persons for employment.' Report p.273 header: 'Circuit County Alcohol Drug Alcohol & Drug Youth Services Mental Health Alt. Ed. TASC UDIS JTPA Other Total'. 96 Stat. 1322 § 2: 'It is the purpose of this Act to establish programs to prepare youth and unskilled adults for entry into the labor force and to afford job training to those economically disadvantaged individuals ...'. 112 Stat. 1059 § 199(b)(2): 'The Job Training Partnership Act (29 U.S.C. 1501 et seq.)' repealed; (c)(2)(B): 'The repeal made by subsection (b)(2) shall take effect on July 1, 2000.'

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf
- https://www.govinfo.gov/content/pkg/STATUTE-96/pdf/STATUTE-96-Pg1322.pdf
- https://www.govinfo.gov/content/pkg/PLAW-105publ220/html/PLAW-105publ220.htm

Model: claude-opus-5-5; reasoning effort: high (orchestration-configured).

## FNC-0488: Ill. S. Ct. R. 23

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 287 (printed page 287), column header "Number of Cases Closed by Rule 23 Order".

Authority type: court_rule; as written: Rule 23; pincite: .

Cited for: Appellate dispositions by Rule 23 order

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 23. Disposition of Cases in the Appellate Court ... (b) Written Order ... (c) Summary Order'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0489: Ill. S. Ct. R. 23

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 288 (printed page 288), repeated column headers "Rule 23" (counted once).

Authority type: court_rule; as written: Rule 23; pincite: .

Cited for: Appellate dispositions by Rule 23 order

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 23. Disposition of Cases in the Appellate Court ... (b) Written Order ... (c) Summary Order'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0490: Ill. S. Ct. R. 23

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 292 (printed page 292), table heading "Rule 23 Orders".

Authority type: court_rule; as written: Rule 23; pincite: .

Cited for: Appellate dispositions by Rule 23 order

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 23. Disposition of Cases in the Appellate Court ... (b) Written Order ... (c) Summary Order'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0491: Ill. S. Ct. R. 23

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 303 (printed page 303), figure caption "Pursuant to Rule 23(b) and (c)".

Authority type: court_rule; as written: Rule 23(b) and (c); pincite: .

Cited for: Appellate dispositions by Rule 23 order

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 23. Disposition of Cases in the Appellate Court ... (b) Written Order ... (c) Summary Order'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0492: Ill. S. Ct. R. 306, 308

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 289 (printed page 289), table footnote.

Authority type: court_rule; as written: S.C.Rule 306/308; pincite: .

Cited for: Permissive interlocutory appeals / certified questions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 306. Interlocutory Appeals by Permission'; 'Rule 308. Certified Questions'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0493: Ill. S. Ct. R. 302(a)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 294 (printed page 294), narrative.

Authority type: court_rule; as written: Rule 302(a); pincite: .

Cited for: Direct civil appeals to the supreme court

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 302. Direct Appeals to the Supreme Court'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0494: Ill. S. Ct. R. 603

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 294 (printed page 294), narrative.

Authority type: court_rule; as written: Rule 603; pincite: .

Cited for: Direct criminal appeals where statute held invalid

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 603. Court To Which Appeal is Taken'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0495: Ill. S. Ct. R. 316

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 294 (printed page 294), narrative.

Authority type: court_rule; as written: Rule 316; pincite: .

Cited for: Certificates of importance

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 316. Appeals from Appellate Court to Supreme Court on Certificate'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0496: Ill. S. Ct. R. 381-384

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 294 (printed page 294), narrative.

Authority type: court_rule; as written: Rules 381, 382, 383, and 384; pincite: .

Cited for: Original action motions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 381. Original Actions ...'; 'Rule 382. Original Actions ...'; 'Rule 383. Motions for Supervisory Orders'; 'Rule 384. Proceedings for the Transfer and Consolidation of Multicircuit Actions.'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0497: Ill. S. Ct. R. 759

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 294 (printed page 294), narrative.

Authority type: court_rule; as written: Rule 759; pincite: .

Cited for: Restoration to active status

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 759. Restoration to Active Status'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0498: Ill. S. Ct. R. 721

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 294 (printed page 294), narrative.

Authority type: court_rule; as written: Rule 721; pincite: .

Cited for: Professional service corporations / law firm registration

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 721. Professional Service Corporations, Professional Associations, Limited Liability Companies, and Registered ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0499: Ill. S. Ct. R. (generally)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 294 (printed page 294), narrative.

Authority type: court_rule; as written: the Supreme Court Rules; pincite: .

Cited for: Miscellaneous docket papers not conforming to the rules

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: Official compiled 'Illinois Supreme Court Rules' (current to Oct. 16, 2026)

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0500: Ill. S. Ct. R. 3

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), narrative.

Authority type: court_rule; as written: Supreme Court Rule 3; pincite: .

Cited for: Proposed Rule Docket

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 3. Rulemaking Procedures'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0501: Ill. S. Ct. R. 716

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), narrative.

Authority type: court_rule; as written: Rule 716; pincite: .

Cited for: House counsel limited admission

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 716. Limited Admission Of House Counsel'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0502: Ill. S. Ct. R. 713

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), narrative.

Authority type: court_rule; as written: Rule 713; pincite: .

Cited for: Foreign legal consultant

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 713. Applications for Licensing of Foreign Legal Consultants'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0503: Ill. S. Ct. R. 717

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), narrative.

Authority type: court_rule; as written: Rule 717; pincite: .

Cited for: Legal service program attorney

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 717. Limited Admission of Legal Service Program Lawyers'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0504: Ill. S. Ct. R. 719

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), narrative.

Authority type: court_rule; as written: Rule 719; pincite: .

Cited for: Military spouse admission

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 719. Admission of Military Spouse Attorneys From Other Jurisdictions'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0505: Ill. S. Ct. R. 721

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), narrative.

Authority type: court_rule; as written: Supreme Court Rule 721; pincite: .

Cited for: Law firm registration

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 721. Professional Service Corporations ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0506: Ill. S. Ct. R. 722

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), narrative.

Authority type: court_rule; as written: Rule 722; pincite: .

Cited for: Limited liability legal practice

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 722. Limited Liability Legal Practice'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0507: Ill. S. Ct. R. 767

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), narrative.

Authority type: court_rule; as written: Supreme Court Rule 767; pincite: .

Cited for: Reinstatement petitions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 767. Reinstatement'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0508: Ill. S. Ct. R. 17

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 17, adopted March 17, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/031723.pdf/amendment" Adopted Mar. 17, 2023, eff. immediately. \*18Rule 1

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0509: Ill. S. Ct. R. 102.1

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 102.1, adopted April 20, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/042023.pdf/amendment" Adopted Apr. 20, 2023, eff. immediately. 

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0510: Ill. S. Ct. R. 242

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 242, adopted April 20, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered April 20, 2023 expressly identifies Rule 242, adopted. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered April 20, 2023: Rule 242, adopted. Effective immediately.

- https://www.illinoiscourts.gov/resources/418f6839-581b-4224-9094-8ea2904ce05a/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0511: Ill. S. Ct. R. 909

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 909, adopted May 24, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/052423.pdf/amendment" Adopted May 24, 2023, eff. immediately. Rules 910-

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0512: Ill. S. Ct. R. 207

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 207, amended January 26, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/012623.pdf/amendment" amended Jan. 26, 2023, eff. immediately . Committee

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0513: Ill. S. Ct. R. 706

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 706, amended January 26, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered January 26, 2023 expressly identifies Rule 706, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered January 26, 2023: Rule 706, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/a24979a1-edab-4c9b-a5de-479b04cff4b3/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0514: Ill. S. Ct. R. 45

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 45, amended February 2, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered February 2, 2023 expressly identifies Rule 45, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered February 2, 2023: Rule 45, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/8a236619-e390-4445-90bd-ce52a1eeb6e7/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0515: Ill. S. Ct. R. 90

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 90, amended February 2, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/020223.pdf/amendment" amended Feb. 2, 2023, eff. immediately ; \* HYPERL

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0516: Ill. S. Ct. R. 101

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 101, amended February 2, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered February 2, 2023 expressly identifies Rule 101, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered February 2, 2023: Rule 101, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/8a236619-e390-4445-90bd-ce52a1eeb6e7/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0517: Ill. S. Ct. R. 218

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 218, amended February 2, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/020223.pdf/amendment" amended Feb. 2, 2023, eff. immediately . Committee

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0518: Ill. S. Ct. R. 241

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 241, amended February 2, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/020223.pdf/amendment" amended Feb. 2, 2023, eff. immediately ; \* HYPERL

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0519: Ill. S. Ct. R. 286

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 286, amended February 2, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered February 2, 2023 expressly identifies Rule 286, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered February 2, 2023: Rule 286, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/8a236619-e390-4445-90bd-ce52a1eeb6e7/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0520: Ill. S. Ct. R. 906

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 906, amended February 27, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/022723.pdf/amendment" amended Feb. 27, 2023, eff. immediately. Committee 

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0521: Ill. S. Ct. R. 908

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 908, amended February 27, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/022723.pdf/amendment" amended Feb. 27, 2023, eff. immediately . Committee

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0522: Ill. S. Ct. R. 39

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 39, amended March 1, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: scourts.gov/files/030123_2.pdf/amendment" amended Mar. 1, 2023, eff. immediately . Committee

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0523: Ill. S. Ct. R. 201

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 201, amended March 17, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: scourts.gov/files/031723.pdf/amendment" ; amended Mar. 17, 2023, eff. immediately . Committee

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0524: Ill. S. Ct. R. 204

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 204, amended March 17, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/031723.pdf/amendment" amended Mar. 17, 2023, eff. immediately . Committee

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0525: Ill. S. Ct. R. 793

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 793, amended April 11, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/041123.pdf/amendment" amended Apr. 11, 2023, eff. immediately ; \*HYPERLI

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0526: Ill. S. Ct. R. 794

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 794, amended April 11, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/041123.pdf/amendment" amended Apr. 11, 2023, eff. immediately ; \* HYPERL

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0527: Ill. S. Ct. R. 795

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 795, amended April 11, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/041123.pdf/amendment" amended Apr. 11, 2023, eff. immediately ; \* HYPERL

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0528: Ill. S. Ct. R. 796

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 796, amended April 11, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/041123.pdf/amendment" amended Apr. 11, 2023, eff. immediately ; \* HYPERL

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0529: Ill. S. Ct. R. 711

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 711, amended April 19, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/041923.pdf/amendment" amended Apr. 19, 2023, eff. immediately ; \*HYPERLI

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0530: Ill. S. Ct. R. 101

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 101, amended April 20, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered April 20, 2023 expressly identifies Rule 101, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered April 20, 2023: Rule 101, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/418f6839-581b-4224-9094-8ea2904ce05a/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0531: Ill. S. Ct. R. 102

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 102, amended April 20, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered April 20, 2023 expressly identifies Rule 102, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered April 20, 2023: Rule 102, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/418f6839-581b-4224-9094-8ea2904ce05a/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0532: Ill. S. Ct. R. 283

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 283, amended April 20, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/042023.pdf/amendment" amended Apr. 20, 2023, eff. immediately . Committee

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0533: Ill. S. Ct. R. 284

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 284, amended April 20, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/042023.pdf/amendment" amended Apr. 20, 2023, eff. immediately . Committee

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0534: Ill. S. Ct. R. 102

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 102, amended April 24, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered April 24, 2023 expressly identifies Rule 102, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered April 24, 2023: Rule 102, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/5b5f1042-5d1d-4f96-8f7d-97a976f30030/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0535: Ill. S. Ct. R. 298

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 298, amended May 20, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The official compiled rules list Rule 298 as 'amended May 30, 2023, eff. Sept. 1, 2023' (order file 053023); the report's 'May 20, 2023' is off by ten days.

Excerpt read: Official compiled rules history: 'amended May 30, 2023, eff. Sept. 1, 2023'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0536: Ill. S. Ct. R. 404

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 404, amended May 20, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The official compiled rules list Rule 404 as 'amended May 30, 2023, eff. Sept. 1, 2023' (order file 053023); the report's 'May 20, 2023' is off by ten days.

Excerpt read: Official compiled rules history: 'amended May 30, 2023, eff. Sept. 1, 2023'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0537: Ill. S. Ct. R. 756

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 756, amended July 6, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered July 6, 2023 expressly identifies Rule 756, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered July 6, 2023: Rule 756, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/6d613af7-e70f-4ff5-b78f-558391c00ef3/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0538: Ill. S. Ct. R. 22

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 22, amended August 2, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: /www.illinoiscourts.gov/files/080223.pdf/amendment" amended Aug. 2, 2023, eff. immediately ; \*HYPERLI

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0539: Ill. S. Ct. R. 404

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 404, amended August 22, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/082223.pdf/amendment" amended Aug. 22, 2023, eff. Sept. 1, 2023 ; \*HYPER

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0540: Ill. S. Ct. R. 604

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 604, amended October 19, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered October 19, 2023 expressly identifies Rule 604, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered October 19, 2023: Rule 604, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/59fd7c8b-e532-4003-a53a-94a61939251b/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0541: Ill. S. Ct. R. 606

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 606, amended October 19, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/101923.pdf/amendment" amended Oct. 19, 2023, eff. immediately ; \* HYPERL

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0542: Ill. S. Ct. R. 299

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 299, amended November 1, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered November 1, 2023 expressly identifies Rule 299, amended. The report gives the order/adoption date. The order makes the amendment effective January 1, 2024; November 1 is the order date.

Excerpt read: Order entered November 1, 2023: Rule 299, amended. Effective January 1, 2024.

- https://www.illinoiscourts.gov/resources/2e30487e-3c56-41a3-8e83-a7295bb78e87/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0543: Ill. S. Ct. R. 46

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 46, amended December 7, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/120723.pdf/amendment" amended Dec. 7, 2023, eff. immediately ; \* HYPERL

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0544: Ill. S. Ct. R. 315

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 315, amended December 7, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered December 7, 2023 expressly identifies Rule 315, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered December 7, 2023: Rule 315, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/049c9542-bf88-4e22-a775-619ccb5eb7f2/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0545: Ill. S. Ct. R. 604

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 604, amended December 7, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered December 7, 2023 expressly identifies Rule 604, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered December 7, 2023: Rule 604, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/049c9542-bf88-4e22-a775-619ccb5eb7f2/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0546: Ill. S. Ct. R. 605

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 605, amended December 7, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered December 7, 2023 expressly identifies Rule 605, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered December 7, 2023: Rule 605, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/049c9542-bf88-4e22-a775-619ccb5eb7f2/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0547: Ill. S. Ct. R. 606

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 606, amended December 7, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/120723.pdf/amendment" amended Dec. 7, 2023, eff. immediately ; \* HYPERL

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0548: Ill. S. Ct. R. 58

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 58, amended December 20, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: oiscourts.gov/files/122023.pdf/amendment" amended Dec. 20, 2023, eff. immediately . Committee

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0549: Ill. S. Ct. R. 404

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 404, corrected September 6, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The amendment history in the official compiled rules lists this date for the rule (linked order).

Excerpt read: scourts.gov/files/090623.pdf/amendment" corrected Sept. 6, 2023, nunc\~pro\~tunc to Sept. 1, 

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0550: Ill. S. Ct. R. 551

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Rule 551, corrected December 20, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered December 20, 2023 expressly identifies Rule 551, correction. The report gives the order/adoption date. The December 20 order corrects a clerical error in the July 18 Rule 551 amendment nunc pro tunc; it does not newly amend Rule 551 in December.

Excerpt read: Order entered December 20, 2023: Rule 551, correction. July 18 Rule 551 effective-date clerical error corrected nunc pro tunc.

- https://www.illinoiscourts.gov/resources/ffab66b4-e893-4c79-833f-03bcbdc71d22/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0551: IRPC 1.15A, 1.15B, 1.15C

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: IRPC 1.15A, 1.15B, 1.15C, adopted March 1, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered March 1, 2023 expressly identifies IRPC 1.15A, 1.15B, 1.15C, adopted. The report gives the order/adoption date. The order expressly makes these changes effective July 1, 2023; March 1 is the adoption/amendment order date, not the effective date.

Excerpt read: Order entered March 1, 2023: IRPC 1.15A, 1.15B, 1.15C, adopted. Effective July 1, 2023.

- https://www.illinoiscourts.gov/resources/be30ae40-c75e-4276-8b69-b0478b0b4184/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0552: Illinois Rule of Evidence 803

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Illinois Rule of Evidence 803, amended January 25, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered January 25, 2023 expressly identifies Illinois Rule of Evidence 803, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered January 25, 2023: Illinois Rule of Evidence 803, amended. Effective immediately.

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/8278e1cb-1f3c-492c-bb70-e9c3a458c333/012523.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0553: IRPC 1.5 and 1.15

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: IRPC 1.5 and 1.15, amended March 1, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered March 1, 2023 expressly identifies IRPC 1.5 and 1.15, amended. The report gives the order/adoption date. The order expressly makes these changes effective July 1, 2023; March 1 is the adoption/amendment order date, not the effective date.

Excerpt read: Order entered March 1, 2023: IRPC 1.5 and 1.15, amended. Effective July 1, 2023.

- https://www.illinoiscourts.gov/resources/be30ae40-c75e-4276-8b69-b0478b0b4184/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0554: Illinois Code of Judicial Conduct of 2023, Canon 2, Rule 2.11

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: Illinois Code of Judicial Conduct of 2023, Canon 2, Rule 2.11, amended May 17, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered May 17, 2023 expressly identifies Canon 2, Rule 2.11, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered May 17, 2023: Canon 2, Rule 2.11, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/70e20cc1-b2d0-46f6-a18d-5845d2ab4521/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0555: IRPC 1.0, 1.1, 1.16, and 7.2

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 295 (printed page 295), 2023 rule adoptions and amendments list.

Authority type: court_rule; as written: IRPC 1.0, 1.1, 1.16, and 7.2, amended July 6, 2023; pincite: .

Cited for: 2023 rulemaking activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The signed Illinois Supreme Court order entered July 6, 2023 expressly identifies IRPC 1.0, 1.1, 1.16, 7.2, amended. The report gives the order/adoption date. The order says effective immediately.

Excerpt read: Order entered July 6, 2023: IRPC 1.0, 1.1, 1.16, 7.2, amended. Effective immediately.

- https://www.illinoiscourts.gov/resources/6d613af7-e70f-4ff5-b78f-558391c00ef3/file
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

### Second check: not required


## FNC-0556: Ill. S. Ct. R. 302(a), 603

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 296 (printed page 296), Table 1 notes.

Authority type: court_rule; as written: Rules 302(a) and 603; pincite: .

Cited for: Direct appeals where statutes held invalid

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 302. Direct Appeals to the Supreme Court'; 'Rule 603. Court To Which Appeal is Taken'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0557: Ill. S. Ct. R. 316

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 296 (printed page 296), Table 1 notes.

Authority type: court_rule; as written: Rule 316; pincite: .

Cited for: Certificate of importance

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 316. Appeals from Appellate Court to Supreme Court on Certificate'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0558: Ill. S. Ct. R. 302(b)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 296 (printed page 296), Table 1 notes.

Authority type: court_rule; as written: Rule 302(b); pincite: .

Cited for: Expedited direct appeal motions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 302. Direct Appeals to the Supreme Court'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0559: Ill. S. Ct. R. 381

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 296 (printed page 296), Table 1 notes.

Authority type: court_rule; as written: Rule 381; pincite: .

Cited for: Mandamus, prohibition, habeas corpus

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 381. Original Actions in the Supreme Court Pursuant to Article VI, Section 4(a), of the Constitution'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0560: Ill. S. Ct. R. 382

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 296 (printed page 296), Table 1 notes.

Authority type: court_rule; as written: Rule 382; pincite: .

Cited for: Legislative redistricting / governor

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 382. Original Actions ... Pursuant to Article IV, Section 3, and Article V, Section 6(d) ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0561: Ill. S. Ct. R. 383

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 296 (printed page 296), Table 1 notes.

Authority type: court_rule; as written: Rule 383; pincite: .

Cited for: Supervisory authority

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 383. Motions for Supervisory Orders'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0562: Ill. S. Ct. R. 384

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 296 (printed page 296), Table 1 notes.

Authority type: court_rule; as written: Rule 384; pincite: .

Cited for: Transfer and consolidation of multicircuit actions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 384. Proceedings for the Transfer and Consolidation of Multicircuit Actions.'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0563: Ill. S. Ct. R. 305

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 296 (printed page 296), Table 1 notes.

Authority type: court_rule; as written: Rule 305; pincite: .

Cited for: Motions to stay

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 305. Stay of Judgments Pending Appeal'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0564: Ill. S. Ct. R. 20

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 296 (printed page 296), Table 1 notes.

Authority type: court_rule; as written: Rule 20; pincite: .

Cited for: Certified questions from federal courts

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 20. Certification of Questions of State Law From Certain Federal Courts'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0565: Ill. S. Ct. R. 759

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 296 (printed page 296), Table 1 notes.

Authority type: court_rule; as written: Rule 759; pincite: .

Cited for: Restoration to active status

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 759. Restoration to Active Status'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0566: Ill. S. Ct. R. 721

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 296 (printed page 296), Table 1 notes.

Authority type: court_rule; as written: Rule 721; pincite: .

Cited for: Law firm registration

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 721. ...'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0567: Ill. S. Ct. R. 315, 317

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 297 (printed page 297), Table 2 title.

Authority type: court_rule; as written: Rules 315/317; pincite: .

Cited for: Petitions for leave to appeal / appeals as of right

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 315. Leave to Appeal ...'; 'Rule 317. Appeals from the Appellate Court to the Supreme Court as of Right'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0568: Ill. S. Ct. R. 762(b)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 301 (printed page 301), Table 8.

Authority type: court_rule; as written: Rule 762(b); pincite: .

Cited for: Discipline on consent

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 762. Disbarment and Other Discipline on Consent'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0569: Ill. S. Ct. R. 763

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 301 (printed page 301), Table 8.

Authority type: court_rule; as written: Rule 763; pincite: .

Cited for: Reciprocal discipline

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 763. Reciprocal Discipline and Disability Inactive Status'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0570: Ill. S. Ct. R. 761

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 301 (printed page 301), Table 8.

Authority type: court_rule; as written: Rule 761; pincite: .

Cited for: Interim suspension after conviction

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 761. Conviction of Crime'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0571: Ill. S. Ct. R. 774

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 301 (printed page 301), Table 8.

Authority type: court_rule; as written: Rule 774; pincite: .

Cited for: Interim suspension

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 774. Interim Suspension'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0572: Ill. S. Ct. R. 762(a)

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 301 (printed page 301), Table 8.

Authority type: court_rule; as written: Rule 762(a); pincite: .

Cited for: Voluntary disbarment

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 762. Disbarment and Other Discipline on Consent'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-0573: Ill. S. Ct. R. 753

Document: 2023 Annual Report Statistical Summary.pdf (attachment, assignments 1-2); location: 2023 Annual Report Statistical Summary.pdf, PDF page 301 (printed page 301), Table 8.

Authority type: court_rule; as written: Rule 753; pincite: .

Cited for: Proceedings on Hearing/Review Board recommendation

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Rule exists in the official compiled Illinois Supreme Court Rules (current to Oct. 16, 2026) with the subject the report attributes to it.

Excerpt read: 'Rule 753. Inquiry, Hearing and Review Boards'

- https://ilcourtsaudio.blob.core.windows.net/antilles-resources/resources/54d35482-757b-40f9-96b3-4b6cbb7d6434/S_Ct_Rules_full.rtf

### Second check: not required


## FNC-SECOND-001: Gulf Oil Corp. v. Gilbert, 330 U.S. 501 (1947)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 2, paragraph beginning 'The Gulf Oil Court stated' (extraction line 82).

Authority type: case; as written: The Gulf Oil Court; pincite: .

Cited for: Attributed explanation of the forum non conveniens principle, following a full citation in the preceding sentence

Quotes: []

Context: Named-authority short form omitted as a separate occurrence; full citation appears in FNC-0161.

Fictional by design: False; 

### First check: VERIFIED

Gulf Oil opinion at 330 U.S. 507 states the forum non conveniens principle introduced by this short form.

Excerpt read: Gulf Oil majority, 330 U.S. 507: a court may decline jurisdiction even where a general venue statute authorizes it.

- https://supreme.justia.com/cases/federal/us/330/501/

### Second check: not required


## FNC-SECOND-002: Peile v. Skelgas, Inc., 163 Ill. 2d 323 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 4, paragraph beginning 'Our last full discussion' (extraction line 163).

Authority type: case; as written: In Peile; pincite: .

Cited for: Facts and disposition of the earlier intrastate forum non conveniens matter

Quotes: []

Context: Named-authority short form after a full Peile citation earlier in Guerine.

Fictional by design: False; 

### First check: VERIFIED

Peile primary opinion describes the Pike County furnace explosion and the transfer sequence summarized in Guerine.

Excerpt read: Peile majority, opening facts: propane furnace explosion at plaintiffs Pike County home; later transfer and refiling history.

- https://app.midpage.ai/document/peile-v-skelgas-inc-2127753

### Second check: not required


## FNC-SECOND-003: Torres v. Walsh, 98 Ill. 2d 338 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 6, paragraph beginning 'In Torres' (extraction line 238).

Authority type: case; as written: In Torres; pincite: .

Cited for: Torres litigation facts used as comparator

Quotes: []

Context: A bare named-authority short form introducing a separate case account; neighboring reporter citations are separately counted.

Fictional by design: False; 

### First check: VERIFIED

Torres primary opinion describes the Cook County suit arising from a Sangamon County collision and subsequent hospital care.

Excerpt read: Torres majority, opening facts: Cook County filing, Sangamon County collision and hospital malpractice allegations.

- https://www.neochart.com/catalog/cases/ill-2d/volume_98/0338_01/index.html

### Second check: not required


## FNC-SECOND-004: Torres v. Walsh, 98 Ill. 2d 338 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 7, paragraph beginning 'Unlike Torres, but like Hinshaw' (extraction line 287).

Authority type: case; as written: Unlike Torres; pincite: .

Cited for: Contrast with the present case's dispersed parties and witnesses

Quotes: []

Context: First member of two bare case-name comparisons in one sentence.

Fictional by design: False; 

### First check: VERIFIED

Torres primary opinion shows a concentrated Sangamon County connection, unlike the dispersed connections in Guerine.

Excerpt read: Torres majority, opening facts: crash, hospital and treating defendant physicians and nurses tied to Sangamon County.

- https://www.neochart.com/catalog/cases/ill-2d/volume_98/0338_01/index.html

### Second check: not required


## FNC-SECOND-005: Hinshaw v. Coachmen Industries, Inc., 319 Ill. App. 3d 269 (2001)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 7, paragraph beginning 'Unlike Torres, but like Hinshaw' (extraction line 287).

Authority type: case; as written: like Hinshaw; pincite: .

Cited for: Comparison with dispersed parties and witnesses

Quotes: []

Context: Second member of two bare case-name comparisons in one sentence; full Hinshaw citations appear nearby.

Fictional by design: False; 

### First check: VERIFIED

Hinshaw primary opinion expressly describes relevant witnesses and connections dispersed among eight Illinois counties and two other states.

Excerpt read: Hinshaw majority, discussion following public and private factors: no predominant county among dispersed witnesses and connections.

- https://app.midpage.ai/document/hinshaw-v-coachmen-industries-inc-2182385

### Second check: not required


## FNC-SECOND-006: Bland v. Norfolk & Western Ry. Co., 116 Ill. 2d 217 (1987)

Document: Bradbury v. St. Mary's Hospital.pdf (attachment, assignments 1-2); location: PDF page 4, sentence beginning 'We, however, fail to see' (extraction line 159).

Authority type: case; as written: the holding in Bland; pincite: .

Cited for: Bradbury's rejection of defendants' Bland argument

Quotes: []

Context: The immediately preceding sentence contains a reporter-pin citation to Bland; this is a separate named-authority short form.

Fictional by design: False; 

### First check: VERIFIED

Bland primary majority opinion warns against giving undue weight to a treating physician located in the chosen forum, supporting Bradbury description of the holding.

Excerpt read: Bland majority, 116 Ill. 2d around 227: undue weight on a chosen-forum physician permits manipulation of forum convenience.

- https://app.midpage.ai/document/bland-v-norfolk-western-railway-2210166

### Second check: not required


## FNC-SECOND-007: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 7, paragraph beginning 'In Guerine' (extraction line 284).

Authority type: case; as written: In Guerine; pincite: .

Cited for: Facts of the accident, party residences, witnesses and Cook County suit

Quotes: []

Context: Bare named-authority short form starts the case narrative; subsequent reporter pins do not count this occurrence.

Fictional by design: False; 

### First check: VERIFIED

The separately supplied Guerine opinion PDF pp.1-2 states the Kane/De Kalb/Cook facts and identifies the Cook County suit.

Excerpt read: Guerine attachment PDF p.1: decedent lived in Kane, crash occurred in De Kalb, individual defendant lived in Cook; estate sued in Cook.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-SECOND-008: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 11, paragraph beginning 'We acknowledge the dissent' (extraction lines 481-485).

Authority type: case; as written: Dawdy distinguishable; pincite: .

Cited for: Three grounds for distinguishing Dawdy

Quotes: []

Context: The majority names Dawdy repeatedly without a reporter cite in this paragraph; at least the opening named short form is omitted from the original count.

Fictional by design: False; 

### First check: VERIFIED

Dawdy primary majority opinion supports all three distinctions recounted in the Langenhorst majority: no witness residing in chosen Madison, possible accident-scene view, and an individual defendant resident in proposed Macoupin.

Excerpt read: Dawdy majority paragraphs 10, 34-37, 49-50: Riederer resides in Macoupin; no potential witness resides in Madison; a jury view of the Macoupin scene is a practical consideration.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SECOND-009: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, sentence beginning 'We emphasize that Dawdy did not overrule Guerine' (extraction line 486).

Authority type: case; as written: Dawdy did not overrule; pincite: .

Cited for: Dawdy's relationship to Guerine

Quotes: []

Context: Separate named-authority short form without reporter cite in the sentence.

Fictional by design: False; 

### First check: VERIFIED

Dawdy primary majority opinion distinguishes Guerine in paragraphs 52-55 and applies it; that text does not overrule Guerine.

Excerpt read: Dawdy majority paragraphs 52-55: Guerine is distinguished based on witness locations and Macoupin predominant connection.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SECOND-010: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, Justice Garman dissent, sentence beginning 'We distinguished Guerine in Dawdy' (extraction line 806).

Authority type: case; as written: Guerine; pincite: .

Cited for: Dissent's assertion that Dawdy distinguished Guerine

Quotes: []

Context: Named-authority short form in the dissent, separate from reporter cites in the following sentence.

Fictional by design: False; 

### First check: VERIFIED

Dawdy primary majority opinion expressly calls Guerine distinguishable, supporting this dissent description of the treatment.

Excerpt read: Dawdy majority paragraphs 52-54: Guerine described and distinguished from Dawdy.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SECOND-011: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, Justice Garman dissent, sentence beginning 'We distinguished Guerine in Dawdy' (extraction line 806).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Dissent's description of Dawdy's treatment of Guerine

Quotes: []

Context: Second named-authority short form in the same sentence.

Fictional by design: False; 

### First check: VERIFIED

Dawdy primary majority opinion expressly distinguishes Guerine in paragraphs 52-54.

Excerpt read: Dawdy majority paragraphs 52-54: Guerine rule stated, followed by the different Madison and Macoupin facts.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-001: Peile v. Skelgas, Inc., 163 Ill. 2d 323 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 5, extraction line 184.

Authority type: case; as written: Peile; pincite: .

Cited for: Named case reference in this passage: We reversed the trial court and the appellate court on the merits of the transfer, but the significance of Peile lies less in its obvious outcome and more in its steadfast adherence to the intrastate applicaƟon of forum non conveniens. We acknowledged the frus

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: We reversed the trial court and the appellate court on the merits of the transfer, but the significance of Peile lies less in its obvious outcome and more in its steadfast adherence to the intrastate applicaƟon of forum non conveniens. We acknowledged the frustraƟng liƟgaƟon quagmire created in the wake of

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Peile majority describes the Pike County explosion and refiling, reaffirms intrastate forum non conveniens, and orders transfer to Pike County.

- https://app.midpage.ai/document/peile-v-skelgas-inc-2127753

### Second check: not required


## FNC-SUPP-002: Torres v. Walsh, 98 Ill. 2d 338 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 5, extraction line 193.

Authority type: case; as written: Torres; pincite: .

Cited for: Named case reference in this passage: equitable doctrine of forum non conveniens is necessary because of perceived abuses in its invocaƟon or Ɵme consumed in its resoluƟon. The doctrine that was acƟvated in Torres was designed to give the courts ‘discreƟonary power which should be exercised only i

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: equitable doctrine of forum non conveniens is necessary because of perceived abuses in its invocaƟon or Ɵme consumed in its resoluƟon. The doctrine that was acƟvated in Torres was designed to give the courts ‘discreƟonary power which should be exercised only in excepƟonal circumstances when it has

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Torres majority describes the Cook County suit and Sangamon County accident and medical care, then recognizes intrastate forum non conveniens.

- https://www.neochart.com/catalog/cases/ill-2d/volume_98/0338_01/index.html

### Second check: not required


## FNC-SUPP-003: Torres v. Walsh, 98 Ill. 2d 338 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 5, extraction line 204.

Authority type: case; as written: Torres v. Walsh; pincite: .

Cited for: Named case reference in this passage: Accordingly, we decline the invitaƟon to abandon intrastate transfer of cases when appropriate, under the principles enunciated in Torres v. Walsh.” Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179, 645 N.E.2d 184.

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Accordingly, we decline the invitaƟon to abandon intrastate transfer of cases when appropriate, under the principles enunciated in Torres v. Walsh.” Peile, 163 Ill.2d at 335-36, 206 Ill.Dec. 179, 645 N.E.2d 184.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Torres majority describes the Cook County suit and Sangamon County accident and medical care, then recognizes intrastate forum non conveniens.

- https://www.neochart.com/catalog/cases/ill-2d/volume_98/0338_01/index.html

### Second check: not required


## FNC-SUPP-004: Peile v. Skelgas, Inc., 163 Ill. 2d 323 (1994)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 5, extraction line 206.

Authority type: case; as written: Peile; pincite: .

Cited for: Named case reference in this passage: 184. Since Peile, we have exercised our supervisory authority more than 30 Ɵmes to transfer cases away from plainƟffs' chosen fora. (See appendix.) Obviously, one of the purposes of the forum non

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: 184. Since Peile, we have exercised our supervisory authority more than 30 Ɵmes to transfer cases away from plainƟffs' chosen fora. (See appendix.) Obviously, one of the purposes of the forum non

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Peile majority describes the Pike County explosion and refiling, reaffirms intrastate forum non conveniens, and orders transfer to Pike County.

- https://app.midpage.ai/document/peile-v-skelgas-inc-2127753

### Second check: not required


## FNC-SUPP-005: Gulf Oil Corp. v. Gilbert, 330 U.S. 501 (1947)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 6, extraction line 246.

Authority type: case; as written: Gulf Oil; pincite: .

Cited for: Named case reference in this passage: plainƟffs peƟƟoned this court for mandamus relief. We reviewed Gulf Oil and noted that courts in 18 other states have statutory authority to order intrastate venue transfers. Torres, 98 Ill.2d at 345-47, 74 Ill.Dec. 880, 456 N.E.2d 601. We further

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: plainƟffs peƟƟoned this court for mandamus relief. We reviewed Gulf Oil and noted that courts in 18 other states have statutory authority to order intrastate venue transfers. Torres, 98 Ill.2d at 345-47, 74 Ill.Dec. 880, 456 N.E.2d 601. We further

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Gulf Oil majority at 330 U.S. 507-09 describes the doctrine and its private and public factors.

- https://supreme.justia.com/cases/federal/us/330/501/

### Second check: not required


## FNC-SUPP-006: Gulf Oil Corp. v. Gilbert, 330 U.S. 501 (1947)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 8, extraction line 327.

Authority type: case; as written: Gulf Oil; pincite: .

Cited for: Named case reference in this passage: congesƟon alone is not disposiƟve. We live in a smaller world than that contemplated by the Gulf Oil Court, or even this court in Torres. Today, we are connected by interstate highways, bustling airways, telecommunicaƟons, and the world

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: congesƟon alone is not disposiƟve. We live in a smaller world than that contemplated by the Gulf Oil Court, or even this court in Torres. Today, we are connected by interstate highways, bustling airways, telecommunicaƟons, and the world

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Gulf Oil majority at 330 U.S. 507-09 describes the doctrine and its private and public factors.

- https://supreme.justia.com/cases/federal/us/330/501/

### Second check: not required


## FNC-SUPP-007: Torres v. Walsh, 98 Ill. 2d 338 (1983)

Document: First Am Bank v. Guerine.pdf (attachment, assignments 1-2); location: PDF page 8, extraction line 327.

Authority type: case; as written: Torres; pincite: .

Cited for: Named case reference in this passage: congesƟon alone is not disposiƟve. We live in a smaller world than that contemplated by the Gulf Oil Court, or even this court in Torres. Today, we are connected by interstate highways, bustling airways, telecommunicaƟons, and the world

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: congesƟon alone is not disposiƟve. We live in a smaller world than that contemplated by the Gulf Oil Court, or even this court in Torres. Today, we are connected by interstate highways, bustling airways, telecommunicaƟons, and the world

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Torres majority describes the Cook County suit and Sangamon County accident and medical care, then recognizes intrastate forum non conveniens.

- https://www.neochart.com/catalog/cases/ill-2d/volume_98/0338_01/index.html

### Second check: not required


## FNC-SUPP-008: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 4, extraction line 155.

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: Upon reconsideraƟon, the appellate court affirmed the circuit court's denial of defendants' moƟon to transfer. 354 Ill.App.3d 1103, 290 Ill.Dec. 895, 822 N.E.2d 480. AŌer reviewing Guerine and Dawdy, the appellate court examined the public and private interest

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Upon reconsideraƟon, the appellate court affirmed the circuit court's denial of defendants' moƟon to transfer. 354 Ill.App.3d 1103, 290 Ill.Dec. 895, 822 N.E.2d 480. AŌer reviewing Guerine and Dawdy, the appellate court examined the public and private interest factors and held that the circuit court of St.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-009: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 4, extraction line 155.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: Upon reconsideraƟon, the appellate court affirmed the circuit court's denial of defendants' moƟon to transfer. 354 Ill.App.3d 1103, 290 Ill.Dec. 895, 822 N.E.2d 480. AŌer reviewing Guerine and Dawdy, the appellate court examined the public and private interest

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Upon reconsideraƟon, the appellate court affirmed the circuit court's denial of defendants' moƟon to transfer. 354 Ill.App.3d 1103, 290 Ill.Dec. 895, 822 N.E.2d 480. AŌer reviewing Guerine and Dawdy, the appellate court examined the public and private interest factors and held that the circuit court of St.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-010: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 7, extraction line 298, Dawdy occurrence 2 on line.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: This court again had the opportunity to review the doctrine of intrastate forum non conveniens in Dawdy, 207 Ill.2d 167, 278 Ill.Dec. 92, 797 N.E.2d 687. In Dawdy, the plainƟff, a Green County resident, was injured in an accident involving a truck driven by a 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: This court again had the opportunity to review the doctrine of intrastate forum non conveniens in Dawdy, 207 Ill.2d 167, 278 Ill.Dec. 92, 797 N.E.2d 687. In Dawdy, the plainƟff, a Green County resident, was injured in an accident involving a truck driven by a Union Pacific employee in Macoupin County.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-011: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 8, extraction line 334.

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: 183, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court disƟnguished Guerine on the basis that, in Dawdy, none of the witnesses resided in the plainƟff's chosen forum. Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687. The court

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: 183, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court disƟnguished Guerine on the basis that, in Dawdy, none of the witnesses resided in the plainƟff's chosen forum. Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687. The court

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-012: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 8, extraction line 347.

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: and that the balance of factors strongly favors transfer . In the instant case, like Guerine, both St. Clair County and Clinton County have significant Ɵes to the case and the potenƟal witnesses are scaƩered throughout several counƟes in the state, as well as 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: and that the balance of factors strongly favors transfer . In the instant case, like Guerine, both St. Clair County and Clinton County have significant Ɵes to the case and the potenƟal witnesses are scaƩered throughout several counƟes in the state, as well as Indiana and

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-013: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 11, extraction line 481.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: defendants as well as plainƟff. We acknowledge the dissent's belief that today's opinion is at odds with Dawdy. However, we find Dawdy disƟnguishable on three grounds. First, in Dawdy, none of the witnesses resided in the

Quotes: []

Context: Separate introductory mention at line 481; FNC-SECOND-008 covers the first Dawdy at line 482. Extraction context: defendants as well as plainƟff. We acknowledge the dissent's belief that today's opinion is at odds with Dawdy. However, we find Dawdy disƟnguishable on three grounds. First, in Dawdy, none of the witnesses resided in the

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-014: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 11, extraction line 482, Dawdy occurrence 2 on line.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: We acknowledge the dissent's belief that today's opinion is at odds with Dawdy. However, we find Dawdy disƟnguishable on three grounds. First, in Dawdy, none of the witnesses resided in the plainƟff's chosen forum. Second, in Dawdy, the possibility of a jury v

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: We acknowledge the dissent's belief that today's opinion is at odds with Dawdy. However, we find Dawdy disƟnguishable on three grounds. First, in Dawdy, none of the witnesses resided in the plainƟff's chosen forum. Second, in Dawdy, the possibility of a jury view of the accident scene was a

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-015: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 11, extraction line 483.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: Dawdy disƟnguishable on three grounds. First, in Dawdy, none of the witnesses resided in the plainƟff's chosen forum. Second, in Dawdy, the possibility of a jury view of the accident scene was a pracƟcal consideraƟon. Finally, in Dawdy, the defendant railroad 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Dawdy disƟnguishable on three grounds. First, in Dawdy, none of the witnesses resided in the plainƟff's chosen forum. Second, in Dawdy, the possibility of a jury view of the accident scene was a pracƟcal consideraƟon. Finally, in Dawdy, the defendant railroad was aƩempƟng to transfer the cause

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-016: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 11, extraction line 484.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: plainƟff's chosen forum. Second, in Dawdy, the possibility of a jury view of the accident scene was a pracƟcal consideraƟon. Finally, in Dawdy, the defendant railroad was aƩempƟng to transfer the cause to the defendant employee's county of residence.

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: plainƟff's chosen forum. Second, in Dawdy, the possibility of a jury view of the accident scene was a pracƟcal consideraƟon. Finally, in Dawdy, the defendant railroad was aƩempƟng to transfer the cause to the defendant employee's county of residence.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-017: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 11, extraction line 486, Guerine occurrence 1 on line.

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: to the defendant employee's county of residence. We emphasize that Dawdy did not overrule Guerine. Dawdy is not irreconcilable with Guerine, nor does it conflict with Guerine. Indeed, in Dawdy, this court expressly disƟnguished the circumstances

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: to the defendant employee's county of residence. We emphasize that Dawdy did not overrule Guerine. Dawdy is not irreconcilable with Guerine, nor does it conflict with Guerine. Indeed, in Dawdy, this court expressly disƟnguished the circumstances

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-018: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 11, extraction line 486, Dawdy occurrence 2 on line.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: to the defendant employee's county of residence. We emphasize that Dawdy did not overrule Guerine. Dawdy is not irreconcilable with Guerine, nor does it conflict with Guerine. Indeed, in Dawdy, this court expressly disƟnguished the circumstances

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: to the defendant employee's county of residence. We emphasize that Dawdy did not overrule Guerine. Dawdy is not irreconcilable with Guerine, nor does it conflict with Guerine. Indeed, in Dawdy, this court expressly disƟnguished the circumstances

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-019: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 11, extraction line 486, Guerine occurrence 2 on line.

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: to the defendant employee's county of residence. We emphasize that Dawdy did not overrule Guerine. Dawdy is not irreconcilable with Guerine, nor does it conflict with Guerine. Indeed, in Dawdy, this court expressly disƟnguished the circumstances

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: to the defendant employee's county of residence. We emphasize that Dawdy did not overrule Guerine. Dawdy is not irreconcilable with Guerine, nor does it conflict with Guerine. Indeed, in Dawdy, this court expressly disƟnguished the circumstances

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-020: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 11, extraction line 487.

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: We emphasize that Dawdy did not overrule Guerine. Dawdy is not irreconcilable with Guerine, nor does it conflict with Guerine. Indeed, in Dawdy, this court expressly disƟnguished the circumstances 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: We emphasize that Dawdy did not overrule Guerine. Dawdy is not irreconcilable with Guerine, nor does it conflict with Guerine. Indeed, in Dawdy, this court expressly disƟnguished the circumstances 

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-021: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 11, extraction line 487.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: We emphasize that Dawdy did not overrule Guerine. Dawdy is not irreconcilable with Guerine, nor does it conflict with Guerine. Indeed, in Dawdy, this court expressly disƟnguished the circumstances 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: We emphasize that Dawdy did not overrule Guerine. Dawdy is not irreconcilable with Guerine, nor does it conflict with Guerine. Indeed, in Dawdy, this court expressly disƟnguished the circumstances 

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-022: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 491, Guerine occurrence 1 on line.

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage:  presented from those presented in Guerine and noted that Guerine was based on the totality of the circumstances. Dawdy, 207 Ill.2d at 183-84, 278 Ill.Dec. 92, 797 N.E.2d 687.

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context:  presented from those presented in Guerine and noted that Guerine was based on the totality of the circumstances. Dawdy, 207 Ill.2d at 183-84, 278 Ill.Dec. 92, 797 N.E.2d 687.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-023: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 491, Guerine occurrence 2 on line.

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage:  presented from those presented in Guerine and noted that Guerine was based on the totality of the circumstances. Dawdy, 207 Ill.2d at 183-84, 278 Ill.Dec. 92, 797 N.E.2d 687.

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context:  presented from those presented in Guerine and noted that Guerine was based on the totality of the circumstances. Dawdy, 207 Ill.2d at 183-84, 278 Ill.Dec. 92, 797 N.E.2d 687.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-024: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 510 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: Less than three years ago, this court addressed the doctrine of forum non conveniens in Dawdy v. Union Pacific R.R. Co., 207 Ill.2d 167, 278 Ill.Dec. 92, 797 N.E.2d 687 (2003). Dawdy was decided in the wake of First American Bank v. Guerine, 198 Ill.2d 511, 26

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Less than three years ago, this court addressed the doctrine of forum non conveniens in Dawdy v. Union Pacific R.R. Co., 207 Ill.2d 167, 278 Ill.Dec. 92, 797 N.E.2d 687 (2003). Dawdy was decided in the wake of First American Bank v. Guerine, 198 Ill.2d 511, 261 Ill.Dec. 763, 764 N.E.2d 54 (2002), another forum

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-025: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 514 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: the circuit court's denial of their moƟon to transfer venue from St. Clair County to Clinton County. We ordered the appellate court to reconsider its judgment in light of Dawdy and Guerine. In affirming the judgment of the circuit court on remand, the appellat

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: the circuit court's denial of their moƟon to transfer venue from St. Clair County to Clinton County. We ordered the appellate court to reconsider its judgment in light of Dawdy and Guerine. In affirming the judgment of the circuit court on remand, the appellate court speculated that it would not have been

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-026: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 514 (Garman, J., dissenting).

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: the circuit court's denial of their moƟon to transfer venue from St. Clair County to Clinton County. We ordered the appellate court to reconsider its judgment in light of Dawdy and Guerine. In affirming the judgment of the circuit court on remand, the appellat

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: the circuit court's denial of their moƟon to transfer venue from St. Clair County to Clinton County. We ordered the appellate court to reconsider its judgment in light of Dawdy and Guerine. In affirming the judgment of the circuit court on remand, the appellate court speculated that it would not have been

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-027: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 516 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: judgment of the circuit court on remand, the appellate court speculated that it would not have been “ordered to reconsider a venue transfer quesƟon in light of both Dawdy and Guerine if the supreme court did not think both decisions sƟll represented good law.”

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: judgment of the circuit court on remand, the appellate court speculated that it would not have been “ordered to reconsider a venue transfer quesƟon in light of both Dawdy and Guerine if the supreme court did not think both decisions sƟll represented good law.” 354 Ill.App.3d 1103, 1109, 290 Ill.Dec.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-028: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 516 (Garman, J., dissenting).

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: judgment of the circuit court on remand, the appellate court speculated that it would not have been “ordered to reconsider a venue transfer quesƟon in light of both Dawdy and Guerine if the supreme court did not think both decisions sƟll represented good law.”

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: judgment of the circuit court on remand, the appellate court speculated that it would not have been “ordered to reconsider a venue transfer quesƟon in light of both Dawdy and Guerine if the supreme court did not think both decisions sƟll represented good law.” 354 Ill.App.3d 1103, 1109, 290 Ill.Dec.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-029: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 518 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: court did not think both decisions sƟll represented good law.” 354 Ill.App.3d 1103, 1109, 290 Ill.Dec. 895, 822 N.E.2d 480. UnƟl today, Dawdy and Guerine did both represent good law, but the majority's decision places this case directly at odds with Dawdy, sig

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: court did not think both decisions sƟll represented good law.” 354 Ill.App.3d 1103, 1109, 290 Ill.Dec. 895, 822 N.E.2d 480. UnƟl today, Dawdy and Guerine did both represent good law, but the majority's decision places this case directly at odds with Dawdy, significantly obscuring our forum non conveniens

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-030: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 518 (Garman, J., dissenting).

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: court did not think both decisions sƟll represented good law.” 354 Ill.App.3d 1103, 1109, 290 Ill.Dec. 895, 822 N.E.2d 480. UnƟl today, Dawdy and Guerine did both represent good law, but the majority's decision places this case directly at odds with Dawdy, sig

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: court did not think both decisions sƟll represented good law.” 354 Ill.App.3d 1103, 1109, 290 Ill.Dec. 895, 822 N.E.2d 480. UnƟl today, Dawdy and Guerine did both represent good law, but the majority's decision places this case directly at odds with Dawdy, significantly obscuring our forum non conveniens

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-031: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 519 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: 895, 822 N.E.2d 480. UnƟl today, Dawdy and Guerine did both represent good law, but the majority's decision places this case directly at odds with Dawdy, significantly obscuring our forum non conveniens jurisprudence. Accordingly, I dissent.

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: 895, 822 N.E.2d 480. UnƟl today, Dawdy and Guerine did both represent good law, but the majority's decision places this case directly at odds with Dawdy, significantly obscuring our forum non conveniens jurisprudence. Accordingly, I dissent.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-032: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 521 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: jurisprudence. Accordingly, I dissent. I. Divergence From Dawdy In Dawdy, the plainƟff, a resident of Greene County, was driving a tractor in Macoupin County when he

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: jurisprudence. Accordingly, I dissent. I. Divergence From Dawdy In Dawdy, the plainƟff, a resident of Greene County, was driving a tractor in Macoupin County when he

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-033: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 12, extraction line 522 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: I. Divergence From Dawdy In Dawdy, the plainƟff, a resident of Greene County, was driving a tractor in Macoupin County when he collided with a truck operated by an employee of the Union Pacific Railroad Company (Union Pacific).

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: I. Divergence From Dawdy In Dawdy, the plainƟff, a resident of Greene County, was driving a tractor in Macoupin County when he collided with a truck operated by an employee of the Union Pacific Railroad Company (Union Pacific).

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-034: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 14, extraction line 608 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: transfer venue (Dawdy, 207 Ill.2d at 185, 278 Ill.Dec. 92, 797 N.E.2d 687). The majority disregards significant aspects of our analysis in Dawdy in affirming the circuit court's denial of defendants' moƟon to transfer in this cause. This disregard begins with 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: transfer venue (Dawdy, 207 Ill.2d at 185, 278 Ill.Dec. 92, 797 N.E.2d 687). The majority disregards significant aspects of our analysis in Dawdy in affirming the circuit court's denial of defendants' moƟon to transfer in this cause. This disregard begins with its discussion of the private

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-035: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 14, extraction line 610 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: of defendants' moƟon to transfer in this cause. This disregard begins with its discussion of the private interest factors in the forum non conveniens analysis. IniƟally, the majority ignores Dawdy's conclusion that the possibility of viewing the accident site,

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: of defendants' moƟon to transfer in this cause. This disregard begins with its discussion of the private interest factors in the forum non conveniens analysis. IniƟally, the majority ignores Dawdy's conclusion that the possibility of viewing the accident site, not the necessity of doing so, is the relevant

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-036: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 14, extraction line 613 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: consideraƟon in weighing this factor. Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. As we noted in Dawdy, “the necessity or propriety of viewing the scene is a decision leŌ within the discreƟon of the trial court.” Dawdy, 207 Ill.2d at 179, 278 Il

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: consideraƟon in weighing this factor. Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. As we noted in Dawdy, “the necessity or propriety of viewing the scene is a decision leŌ within the discreƟon of the trial court.” Dawdy, 207 Ill.2d at 179, 278 Ill.Dec. 92, 797 N.E.2d 687. The majority concludes that

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-037: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 15, extraction line 629 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: Next, in evaluaƟng the relaƟve ease of access to tesƟmonial evidence, the majority fails to conduct a balanced analysis of the residency of potenƟal witnesses. As menƟoned, in Dawdy, we focused primarily on the facts that two of the potenƟal witnesses resided 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Next, in evaluaƟng the relaƟve ease of access to tesƟmonial evidence, the majority fails to conduct a balanced analysis of the residency of potenƟal witnesses. As menƟoned, in Dawdy, we focused primarily on the facts that two of the potenƟal witnesses resided in Macoupin County, none resided in

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-038: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 15, extraction line 662 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: There is no perfect equaƟon for determining whether access to potenƟal witnesses is easier in one county than in another, but if, in Dawdy, Macoupin County provided easier access to witnesses than Madison County, then we can certainly say the same of Clinton C

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: There is no perfect equaƟon for determining whether access to potenƟal witnesses is easier in one county than in another, but if, in Dawdy, Macoupin County provided easier access to witnesses than Madison County, then we can certainly say the same of Clinton County vis-à-vis St. Clair County in this

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-039: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 15, extraction line 664 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: Madison County, then we can certainly say the same of Clinton County vis-à-vis St. Clair County in this case. Here, in contrast to Dawdy, a significantly larger proporƟon of the potenƟal witnesses resides in 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Madison County, then we can certainly say the same of Clinton County vis-à-vis St. Clair County in this case. Here, in contrast to Dawdy, a significantly larger proporƟon of the potenƟal witnesses resides in 

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-040: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 16, extraction line 668 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage:  the transferee county, and like Dawdy, the potenƟal witnesses appear, on the whole, to reside closer to the transferee county than to the county where suit was filed. It is true that two potenƟal witnesses

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context:  the transferee county, and like Dawdy, the potenƟal witnesses appear, on the whole, to reside closer to the transferee county than to the county where suit was filed. It is true that two potenƟal witnesses

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-041: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 16, extraction line 679 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: residencies of all the other potenƟal witnesses. The majority also contradicts Dawdy's discussion of other pracƟcal consideraƟons relevant to the forum non conveniens analysis. Specifically, the majority ignores our refusal in Dawdy to “accept the

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: residencies of all the other potenƟal witnesses. The majority also contradicts Dawdy's discussion of other pracƟcal consideraƟons relevant to the forum non conveniens analysis. Specifically, the majority ignores our refusal in Dawdy to “accept the

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-042: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 16, extraction line 688 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: potenƟal witnesses, which, as discussed above, favors Clinton County. In addiƟon to disregarding Dawdy's analysis of the private interest forum non conveniens factors, the majority also departs from Dawdy's analysis of the public interest factors. In Dawdy, wi

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: potenƟal witnesses, which, as discussed above, favors Clinton County. In addiƟon to disregarding Dawdy's analysis of the private interest forum non conveniens factors, the majority also departs from Dawdy's analysis of the public interest factors. In Dawdy, with respect to the

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-043: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 16, extraction line 689, Dawdy occurrence 1 on line (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: In addiƟon to disregarding Dawdy's analysis of the private interest forum non conveniens factors, the majority also departs from Dawdy's analysis of the public interest factors. In Dawdy, with respect to the local interests in deciding the controversy, we decl

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: In addiƟon to disregarding Dawdy's analysis of the private interest forum non conveniens factors, the majority also departs from Dawdy's analysis of the public interest factors. In Dawdy, with respect to the local interests in deciding the controversy, we declined to aƩach disposiƟve significance to the fact the

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-044: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 16, extraction line 689, Dawdy occurrence 2 on line (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: In addiƟon to disregarding Dawdy's analysis of the private interest forum non conveniens factors, the majority also departs from Dawdy's analysis of the public interest factors. In Dawdy, with respect to the local interests in deciding the controversy, we decl

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: In addiƟon to disregarding Dawdy's analysis of the private interest forum non conveniens factors, the majority also departs from Dawdy's analysis of the public interest factors. In Dawdy, with respect to the local interests in deciding the controversy, we declined to aƩach disposiƟve significance to the fact the

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-045: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 16, extraction line 703 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: extent of each county's local interest in this case. As menƟoned, in evaluaƟng this factor in Dawdy, we found it significant that the accident occurred in the transferee county; that the plainƟff did not reside in the county where suit was filed; that the indi

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: extent of each county's local interest in this case. As menƟoned, in evaluaƟng this factor in Dawdy, we found it significant that the accident occurred in the transferee county; that the plainƟff did not reside in the county where suit was filed; that the individual

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-046: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 17, extraction line 714 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: that the accident occurred in Macoupin County gives the acƟon a local interest”). In this case, as in Dawdy, the accident occurred in the transferee county. Moreover, the plainƟff and the individual defendants do not reside in the county where suit was filed. 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: that the accident occurred in Macoupin County gives the acƟon a local interest”). In this case, as in Dawdy, the accident occurred in the transferee county. Moreover, the plainƟff and the individual defendants do not reside in the county where suit was filed. As for the potenƟal witnesses, they

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-047: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 17, extraction line 717 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: appear, on the whole, to reside closer to the transferee county than to the county where suit was filed, and a larger proporƟon of them actually resides in the transferee county than was the case in Dawdy. The only disƟncƟon between this case and Dawdy in term

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: appear, on the whole, to reside closer to the transferee county than to the county where suit was filed, and a larger proporƟon of them actually resides in the transferee county than was the case in Dawdy. The only disƟncƟon between this case and Dawdy in terms of the consideraƟons in quesƟon is that,

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-048: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 17, extraction line 718 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: and a larger proporƟon of them actually resides in the transferee county than was the case in Dawdy. The only disƟncƟon between this case and Dawdy in terms of the consideraƟons in quesƟon is that, here, none of the individual defendants reside in the transfer

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: and a larger proporƟon of them actually resides in the transferee county than was the case in Dawdy. The only disƟncƟon between this case and Dawdy in terms of the consideraƟons in quesƟon is that, here, none of the individual defendants reside in the transferee county. However, the significance of

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-049: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 17, extraction line 720 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: here, none of the individual defendants reside in the transferee county. However, the significance of this disƟncƟon is offset by the fact that plainƟff, unlike the plainƟff in Dawdy, is a resident of the transferee county. In Dawdy, the plainƟff was a residen

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: here, none of the individual defendants reside in the transferee county. However, the significance of this disƟncƟon is offset by the fact that plainƟff, unlike the plainƟff in Dawdy, is a resident of the transferee county. In Dawdy, the plainƟff was a resident of Greene County, suit was filed in Madison

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-050: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 17, extraction line 721 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: this disƟncƟon is offset by the fact that plainƟff, unlike the plainƟff in Dawdy, is a resident of the transferee county. In Dawdy, the plainƟff was a resident of Greene County, suit was filed in Madison County, and the defendants wished to transfer venue to M

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: this disƟncƟon is offset by the fact that plainƟff, unlike the plainƟff in Dawdy, is a resident of the transferee county. In Dawdy, the plainƟff was a resident of Greene County, suit was filed in Madison County, and the defendants wished to transfer venue to Macoupin County. Dawdy, 207 Ill.2d at 169-70,

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-051: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 17, extraction line 726 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: In sum, based on the very same consideraƟons we took into account in evaluaƟng the nature and extent of the local interests at play in Dawdy, it is clear that the controversy at issue here is local to Clinton County, and that Clinton County has a strong intere

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: In sum, based on the very same consideraƟons we took into account in evaluaƟng the nature and extent of the local interests at play in Dawdy, it is clear that the controversy at issue here is local to Clinton County, and that Clinton County has a strong interest in resolving it. The majority unduly emphasizes

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-052: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 17, extraction line 739 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: Finally, in assessing court congesƟon, the majority fails to examine the staƟsƟcal criteria we considered in Dawdy and instead focuses solely on the circuit court judge's assessment of the St. Clair County circuit court's docket. 219 Ill.2d at 451-52, 302 Ill.

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Finally, in assessing court congesƟon, the majority fails to examine the staƟsƟcal criteria we considered in Dawdy and instead focuses solely on the circuit court judge's assessment of the St. Clair County circuit court's docket. 219 Ill.2d at 451-52, 302 Ill.Dec. at 375-76, 848 N.E.2d at 939-40. In Dawdy, we looked

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-053: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 17, extraction line 740 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: in Dawdy and instead focuses solely on the circuit court judge's assessment of the St. Clair County circuit court's docket. 219 Ill.2d at 451-52, 302 Ill.Dec. at 375-76, 848 N.E.2d at 939-40. In Dawdy, we looked to the overall number of pending jury acƟons for

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: in Dawdy and instead focuses solely on the circuit court judge's assessment of the St. Clair County circuit court's docket. 219 Ill.2d at 451-52, 302 Ill.Dec. at 375-76, 848 N.E.2d at 939-40. In Dawdy, we looked to the overall number of pending jury acƟons for damages over $50,000 and the Ɵme to verdict for such

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-054: Boner v. Peabody Coal Co., 142 Ill. 2d 523 (1991)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 18, extraction line 760 (Garman, J., dissenting).

Authority type: case; as written: Boner; pincite: .

Cited for: Named case reference in this passage: a reviewing court should turn a blind eye to objecƟve data in weighing one venue's congesƟon against another's. Boner, in fact, did consider court data in arriving at its conclusion that court congesƟon did not necessitate transferring the acƟon at issue to Ga

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: a reviewing court should turn a blind eye to objecƟve data in weighing one venue's congesƟon against another's. Boner, in fact, did consider court data in arriving at its conclusion that court congesƟon did not necessitate transferring the acƟon at issue to GallaƟn County. Boner, 142 Ill.2d at 539, 154 Ill.Dec.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Boner majority at 142 Ill. 2d 538-39 discusses trial-court docket knowledge and compares 1989 court statistics.

- https://law.justia.com/cases/illinois/supreme-court/1991/69684-7.html

### Second check: not required


## FNC-SUPP-055: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 18, extraction line 767 (Garman, J., dissenting).

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: Clair County. II. Guerine, Dawdy, and the Instant Case It is clear, based on the foregoing, that the majority wishes to distance this court from the reasoning we

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Clair County. II. Guerine, Dawdy, and the Instant Case It is clear, based on the foregoing, that the majority wishes to distance this court from the reasoning we

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-056: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 18, extraction line 767 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: Clair County. II. Guerine, Dawdy, and the Instant Case It is clear, based on the foregoing, that the majority wishes to distance this court from the reasoning we

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Clair County. II. Guerine, Dawdy, and the Instant Case It is clear, based on the foregoing, that the majority wishes to distance this court from the reasoning we

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-057: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 18, extraction line 769, Dawdy occurrence 1 on line (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: It is clear, based on the foregoing, that the majority wishes to distance this court from the reasoning we applied in Dawdy. I cannot endorse this approach, as it erroneously suggests that Dawdy is irreconcilable with Guerine, when, in fact, Dawdy and Guerine 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: It is clear, based on the foregoing, that the majority wishes to distance this court from the reasoning we applied in Dawdy. I cannot endorse this approach, as it erroneously suggests that Dawdy is irreconcilable with Guerine, when, in fact, Dawdy and Guerine can be applied consistently to govern the

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-058: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 18, extraction line 769, Dawdy occurrence 2 on line (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: It is clear, based on the foregoing, that the majority wishes to distance this court from the reasoning we applied in Dawdy. I cannot endorse this approach, as it erroneously suggests that Dawdy is irreconcilable with Guerine, when, in fact, Dawdy and Guerine 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: It is clear, based on the foregoing, that the majority wishes to distance this court from the reasoning we applied in Dawdy. I cannot endorse this approach, as it erroneously suggests that Dawdy is irreconcilable with Guerine, when, in fact, Dawdy and Guerine can be applied consistently to govern the

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-059: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 18, extraction line 770, Guerine occurrence 1 on line (Garman, J., dissenting).

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: applied in Dawdy. I cannot endorse this approach, as it erroneously suggests that Dawdy is irreconcilable with Guerine, when, in fact, Dawdy and Guerine can be applied consistently to govern the outcome of this case.

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: applied in Dawdy. I cannot endorse this approach, as it erroneously suggests that Dawdy is irreconcilable with Guerine, when, in fact, Dawdy and Guerine can be applied consistently to govern the outcome of this case.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-060: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 18, extraction line 770 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: applied in Dawdy. I cannot endorse this approach, as it erroneously suggests that Dawdy is irreconcilable with Guerine, when, in fact, Dawdy and Guerine can be applied consistently to govern the outcome of this case.

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: applied in Dawdy. I cannot endorse this approach, as it erroneously suggests that Dawdy is irreconcilable with Guerine, when, in fact, Dawdy and Guerine can be applied consistently to govern the outcome of this case.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-061: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 18, extraction line 770, Guerine occurrence 2 on line (Garman, J., dissenting).

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: applied in Dawdy. I cannot endorse this approach, as it erroneously suggests that Dawdy is irreconcilable with Guerine, when, in fact, Dawdy and Guerine can be applied consistently to govern the outcome of this case.

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: applied in Dawdy. I cannot endorse this approach, as it erroneously suggests that Dawdy is irreconcilable with Guerine, when, in fact, Dawdy and Guerine can be applied consistently to govern the outcome of this case.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-062: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 18, extraction line 772 (Garman, J., dissenting).

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: outcome of this case. The lawsuit at issue in Guerine arose from a car accident involving the individual defendant and the decedent. Guerine, 198 Ill.2d at 512, 261 Ill.Dec. 763, 764 N.E.2d 54. A boat trailer broke away from

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: outcome of this case. The lawsuit at issue in Guerine arose from a car accident involving the individual defendant and the decedent. Guerine, 198 Ill.2d at 512, 261 Ill.Dec. 763, 764 N.E.2d 54. A boat trailer broke away from

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-063: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 806, Guerine occurrence 2 on line (Garman, J., dissenting).

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: plainƟffs filed suit. Guerine, 198 Ill.2d at 524-25, 261 Ill.Dec. 763, 764 N.E.2d 54. We disƟnguished Guerine in Dawdy. There we observed that, unlike in Guerine, none of the witnesses resided in the county where suit was filed, and the transferee county had a

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: plainƟffs filed suit. Guerine, 198 Ill.2d at 524-25, 261 Ill.Dec. 763, 764 N.E.2d 54. We disƟnguished Guerine in Dawdy. There we observed that, unlike in Guerine, none of the witnesses resided in the county where suit was filed, and the transferee county had a predominant connecƟon to

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-064: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 814 (Garman, J., dissenting).

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: the transferee county had a “predominant connecƟon” to the case, our reasons were implicit in our analysis of the private and public interest factors. Unlike the individual defendant in Guerine, the individual defendant in Dawdy was a resident of the transfere

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: the transferee county had a “predominant connecƟon” to the case, our reasons were implicit in our analysis of the private and public interest factors. Unlike the individual defendant in Guerine, the individual defendant in Dawdy was a resident of the transferee county. See Dawdy, 207 Ill.2d at 170,

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-065: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 815, Dawdy occurrence 1 on line (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: analysis of the private and public interest factors. Unlike the individual defendant in Guerine, the individual defendant in Dawdy was a resident of the transferee county. See Dawdy, 207 Ill.2d at 170, 183, 278 Ill.Dec. 92, 797 N.E.2d 687. In addiƟon, unlike t

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: analysis of the private and public interest factors. Unlike the individual defendant in Guerine, the individual defendant in Dawdy was a resident of the transferee county. See Dawdy, 207 Ill.2d at 170, 183, 278 Ill.Dec. 92, 797 N.E.2d 687. In addiƟon, unlike the mixed negligence-product liability acƟon in

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-066: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 817 (Garman, J., dissenting).

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: 183, 278 Ill.Dec. 92, 797 N.E.2d 687. In addiƟon, unlike the mixed negligence-product liability acƟon in Guerine, all of the plainƟff's negligence claims in Dawdy related to the specific accident at issue, which occurred in the transferee county. See Dawdy, 20

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: 183, 278 Ill.Dec. 92, 797 N.E.2d 687. In addiƟon, unlike the mixed negligence-product liability acƟon in Guerine, all of the plainƟff's negligence claims in Dawdy related to the specific accident at issue, which occurred in the transferee county. See Dawdy, 207 Ill.2d at 169, 183, 278 Ill.Dec. 92, 797 N.E.2d 687.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-067: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 817 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: 183, 278 Ill.Dec. 92, 797 N.E.2d 687. In addiƟon, unlike the mixed negligence-product liability acƟon in Guerine, all of the plainƟff's negligence claims in Dawdy related to the specific accident at issue, which occurred in the transferee county. See Dawdy, 20

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: 183, 278 Ill.Dec. 92, 797 N.E.2d 687. In addiƟon, unlike the mixed negligence-product liability acƟon in Guerine, all of the plainƟff's negligence claims in Dawdy related to the specific accident at issue, which occurred in the transferee county. See Dawdy, 207 Ill.2d at 169, 183, 278 Ill.Dec. 92, 797 N.E.2d 687.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-068: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 819 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: occurred in the transferee county. See Dawdy, 207 Ill.2d at 169, 183, 278 Ill.Dec. 92, 797 N.E.2d 687. Moreover, the potenƟal witnesses in Dawdy were more closely linked to the transferee county than in Guerine. See Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 7

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: occurred in the transferee county. See Dawdy, 207 Ill.2d at 169, 183, 278 Ill.Dec. 92, 797 N.E.2d 687. Moreover, the potenƟal witnesses in Dawdy were more closely linked to the transferee county than in Guerine. See Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-069: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 820 (Garman, J., dissenting).

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: Moreover, the potenƟal witnesses in Dawdy were more closely linked to the transferee county than in Guerine. See Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. The grounds on which the majority disƟnguishes Dawdy from the instant case are unpersuas

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Moreover, the potenƟal witnesses in Dawdy were more closely linked to the transferee county than in Guerine. See Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. The grounds on which the majority disƟnguishes Dawdy from the instant case are unpersuasive and

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-070: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 821 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: Guerine. See Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. The grounds on which the majority disƟnguishes Dawdy from the instant case are unpersuasive and likely to cause confusion. First, the majority asserts that “in Dawdy, none of the witnesses

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Guerine. See Dawdy, 207 Ill.2d at 178, 278 Ill.Dec. 92, 797 N.E.2d 687. The grounds on which the majority disƟnguishes Dawdy from the instant case are unpersuasive and likely to cause confusion. First, the majority asserts that “in Dawdy, none of the witnesses resided in

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-071: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 822 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: The grounds on which the majority disƟnguishes Dawdy from the instant case are unpersuasive and likely to cause confusion. First, the majority asserts that “in Dawdy, none of the witnesses resided in the plainƟff's chosen forum.” 219 Ill.2d at 453, 302 Ill.Dec

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: The grounds on which the majority disƟnguishes Dawdy from the instant case are unpersuasive and likely to cause confusion. First, the majority asserts that “in Dawdy, none of the witnesses resided in the plainƟff's chosen forum.” 219 Ill.2d at 453, 302 Ill.Dec. at 376, 848 N.E.2d at 940. It is true that, in

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-072: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 827 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: witnesses reside in St. Clair County is relaƟvely inconsequenƟal when considered along with the residencies of all the other potenƟal witnesses. Here, as in Dawdy, the potenƟal witnesses appear, on the whole, to reside closer to the transferee county than to t

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: witnesses reside in St. Clair County is relaƟvely inconsequenƟal when considered along with the residencies of all the other potenƟal witnesses. Here, as in Dawdy, the potenƟal witnesses appear, on the whole, to reside closer to the transferee county than to the county where suit was filed.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-073: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 829 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: the whole, to reside closer to the transferee county than to the county where suit was filed. Second, the majority states that “in Dawdy, the possibility of a jury view of the accident scene was a pracƟcal consideraƟon.” 219 Ill.2d at 453, 302 Ill.Dec. at 376,

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: the whole, to reside closer to the transferee county than to the county where suit was filed. Second, the majority states that “in Dawdy, the possibility of a jury view of the accident scene was a pracƟcal consideraƟon.” 219 Ill.2d at 453, 302 Ill.Dec. at 376, 848 N.E.2d at 940. As discussed, the

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-074: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 19, extraction line 832 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: possibility of a jury view of the accident scene is likewise a pracƟcal consideraƟon in this case. Third, the majority notes that “in Dawdy, the defendant railroad was aƩempƟng to transfer the cause to the defendant employee's county of residence.” 219 Ill.2d 

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: possibility of a jury view of the accident scene is likewise a pracƟcal consideraƟon in this case. Third, the majority notes that “in Dawdy, the defendant railroad was aƩempƟng to transfer the cause to the defendant employee's county of residence.” 219 Ill.2d at 453, 302 Ill.Dec. at 376, 848 N.E.2d at 940.

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-075: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 20, extraction line 855 (Garman, J., dissenting).

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: Clair County. Balancing these consideraƟons, the convenience of the parƟes does not strongly favor one venue over the other. Thus, the fact that transferring this case would not, unlike in Dawdy, place it in the county of residence of one of the defendants has

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Clair County. Balancing these consideraƟons, the convenience of the parƟes does not strongly favor one venue over the other. Thus, the fact that transferring this case would not, unlike in Dawdy, place it in the county of residence of one of the defendants has no bearing on this factor of the forum non

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source. The comparative criticism belongs to the dissent and is not presented as the majority holding.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-076: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430 (2006)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: PDF page 4, extraction line 170.

Authority type: case; as written: Langenhorst; pincite: .

Cited for: Named case reference in this passage: D. No Predominant Connection to Cook County. This case is readily distinguishable from Guerine and Langenhorst, in each of which the Illinois Supreme Court denied transfer because potential witnesses were scattered among several

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: D. No Predominant Connection to Cook County. This case is readily distinguishable from Guerine and Langenhorst, in each of which the Illinois Supreme Court denied transfer because potential witnesses were scattered among several

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Langenhorst majority PDF pages 7-12 describes scattered witnesses and affirms denial of transfer; Garman dissent disagrees.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-SUPP-077: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: PDF page 5, extraction line 182.

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: Clinton County, Indiana, and Missouri, with no predominant connection to either proposed forum. (Langenhorst v. Norfolk Southern.pdf, p.10–p.11.) Here, unlike Guerine and Langenhorst, the situs of the alleged negligence, the residence and location of every Def

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: Clinton County, Indiana, and Missouri, with no predominant connection to either proposed forum. (Langenhorst v. Norfolk Southern.pdf, p.10–p.11.) Here, unlike Guerine and Langenhorst, the situs of the alleged negligence, the residence and location of every Defendant,

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-078: Langenhorst v. Norfolk Southern Ry. Co., 219 Ill. 2d 430 (2006)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: PDF page 5, extraction line 183.

Authority type: case; as written: Langenhorst; pincite: .

Cited for: Named case reference in this passage: forum. (Langenhorst v. Norfolk Southern.pdf, p.10–p.11.) Here, unlike Guerine and Langenhorst, the situs of the alleged negligence, the residence and location of every Defendant, and the location of virtually every standard-of-care witness converge in a single

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: forum. (Langenhorst v. Norfolk Southern.pdf, p.10–p.11.) Here, unlike Guerine and Langenhorst, the situs of the alleged negligence, the residence and location of every Defendant, and the location of virtually every standard-of-care witness converge in a single county —

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Langenhorst majority PDF pages 7-12 describes scattered witnesses and affirms denial of transfer; Garman dissent disagrees.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf

### Second check: not required


## FNC-SUPP-079: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Defendants Motion to Transfer.pdf (attachment, assignments 1-2); location: PDF page 5, extraction line 186.

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: DuPage. This is precisely the “predominant connection” the Supreme Court found lacking in Guerine, and its presence here strongly favors transfer. V. THE PUBLIC INTEREST FACTORS STRONGLY FAVOR TRANSFER TO

Quotes: []

Context: Free-standing named reference omitted from first census. Extraction context: DuPage. This is precisely the “predominant connection” the Supreme Court found lacking in Guerine, and its presence here strongly favors transfer. V. THE PUBLIC INTEREST FACTORS STRONGLY FAVOR TRANSFER TO

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The reference identifies the correct decision and its factual or doctrinal comparison is supported by the source.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-080: First American Bank v. Guerine, 198 Ill. 2d 511 (2002)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 7, extraction line 291.

Authority type: case; as written: Guerine; pincite: .

Cited for: Named case reference in this passage: would be necessary. We evaluated the conƟnued vitality of the intrastate forum non conveniens doctrine in Guerine and reaffirmed the doctrine as Illinois law. Guerine, 198 Ill.2d at 514, 261 Ill.Dec. 763, 764 N.E.2d 54. In

Quotes: []

Context: The prose name is a separate textual occurrence; the reporter pincite following the sentence was already counted. Extraction context: would be necessary. We evaluated the conƟnued vitality of the intrastate forum non conveniens doctrine in Guerine and reaffirmed the doctrine as Illinois law. Guerine, 198 Ill.2d at 514, 261 Ill.Dec. 763, 764 N.E.2d 54. In

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The prose reference correctly identifies the case and the described facts or disposition. The reporter pincite following the sentence remains in the first census and is not repeated.

Excerpt read: Supplied Guerine majority PDF pages 1-8 describes dispersed witnesses and the Cook County connection, and reverses transfer where no county predominated.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf

### Second check: not required


## FNC-SUPP-081: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 7, extraction line 305.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: them resided in Madison County. In applying the forum non conveniens factors, the Dawdy majority concluded that the circuit court abused its discreƟon in denying defendants' moƟon to transfer the cause to Macoupin County. Dawdy,

Quotes: []

Context: The prose name is a separate textual occurrence; the reporter pincite following the sentence was already counted. Extraction context: them resided in Madison County. In applying the forum non conveniens factors, the Dawdy majority concluded that the circuit court abused its discreƟon in denying defendants' moƟon to transfer the cause to Macoupin County. Dawdy,

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The prose reference correctly identifies the case and the described facts or disposition. The reporter pincite following the sentence remains in the first census and is not repeated.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-082: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 7, extraction line 307.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: abused its discreƟon in denying defendants' moƟon to transfer the cause to Macoupin County. Dawdy, 207 Ill.2d at 177, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court first examined the private interest factor of relaƟve ease of access to evidence and determin

Quotes: []

Context: The prose name is a separate textual occurrence; the reporter pincite following the sentence was already counted. Extraction context: abused its discreƟon in denying defendants' moƟon to transfer the cause to Macoupin County. Dawdy, 207 Ill.2d at 177, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court first examined the private interest factor of relaƟve ease of access to evidence and determined that because the locaƟon of the accident

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The prose reference correctly identifies the case and the described facts or disposition. The reporter pincite following the sentence remains in the first census and is not repeated.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-083: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 8, extraction line 322.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: factor should be accorded central emphasis or conclusive effect.” Dawdy, 207 Ill.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687, ciƟng Jones, 93 Ill.2d at 373, 67 Ill.Dec. 118, 444 N.E.2d 157. The Dawdy court concluded that, on a whole, the private interest factor

Quotes: []

Context: The prose name is a separate textual occurrence; the reporter pincite following the sentence was already counted. Extraction context: factor should be accorded central emphasis or conclusive effect.” Dawdy, 207 Ill.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687, ciƟng Jones, 93 Ill.2d at 373, 67 Ill.Dec. 118, 444 N.E.2d 157. The Dawdy court concluded that, on a whole, the private interest factors favored the convenience of Macoupin County

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The prose reference correctly identifies the case and the described facts or disposition. The reporter pincite following the sentence remains in the first census and is not repeated.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-084: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 8, extraction line 325.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: over Madison County. Dawdy, 207 Ill.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court then determined that the public interest factors strongly weighed against Madison County. Dawdy, 207 Ill.2d at 180-81, 278 Ill.Dec. 92, 797 N.E.2d 687. Although the

Quotes: []

Context: The prose name is a separate textual occurrence; the reporter pincite following the sentence was already counted. Extraction context: over Madison County. Dawdy, 207 Ill.2d at 180, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court then determined that the public interest factors strongly weighed against Madison County. Dawdy, 207 Ill.2d at 180-81, 278 Ill.Dec. 92, 797 N.E.2d 687. Although the court recognized

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The prose reference correctly identifies the case and the described facts or disposition. The reporter pincite following the sentence remains in the first census and is not repeated.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-085: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 8, extraction line 334, Dawdy occurrence 1 on line.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: 183, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court disƟnguished Guerine on the basis that, in Dawdy, none of the witnesses resided in the plainƟff's chosen forum. Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687. The court

Quotes: []

Context: The prose name is a separate textual occurrence; the reporter pincite following the sentence was already counted. Extraction context: 183, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court disƟnguished Guerine on the basis that, in Dawdy, none of the witnesses resided in the plainƟff's chosen forum. Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687. The court

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The prose reference correctly identifies the case and the described facts or disposition. The reporter pincite following the sentence remains in the first census and is not repeated.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required


## FNC-SUPP-086: Dawdy v. Union Pacific R.R. Co., 207 Ill. 2d 167 (2003)

Document: Langenhorst v. Norfolk Southern.pdf (attachment, assignments 1-2); location: PDF page 8, extraction line 334, Dawdy occurrence 2 on line.

Authority type: case; as written: Dawdy; pincite: .

Cited for: Named case reference in this passage: 183, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court disƟnguished Guerine on the basis that, in Dawdy, none of the witnesses resided in the plainƟff's chosen forum. Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687. The court

Quotes: []

Context: The prose name is a separate textual occurrence; the reporter pincite following the sentence was already counted. Extraction context: 183, 278 Ill.Dec. 92, 797 N.E.2d 687. The Dawdy court disƟnguished Guerine on the basis that, in Dawdy, none of the witnesses resided in the plainƟff's chosen forum. Dawdy, 207 Ill.2d at 184, 278 Ill.Dec. 92, 797 N.E.2d 687. The court

Fictional by design: False; 

### First check: VERIFIED

Target judicial opinion text was read. The prose reference correctly identifies the case and the described facts or disposition. The reporter pincite following the sentence remains in the first census and is not repeated.

Excerpt read: Dawdy majority paragraphs 8-10 and 34-55 set out the accident, witness locations, possible scene view, court congestion, local interests, transfer, and distinction from Guerine.

- https://openjurist.org/207/ill2d/167/dawdy-v-union-pacific-rr-co-2078377

### Second check: not required
