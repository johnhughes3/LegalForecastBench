# LegalReasonBench citation check

AI-generated citation checks, not human legal verification or score corrections. The counting unit is a citation in a unique matter document, not each repeated assignment packet. Worker file lists and limits are reproduced below; absence of a stated limit does not independently establish exhaustive coverage. Completion requires an explicit census-complete judgment; verification limits remain visible. Every first-check problem requires an independent second check, including overturned findings. Missing files and pending checks never establish a zero-problem result.

[Summary JSON](summary.json) · [Problems and second checks](problems.md) · [Rubric intent](rubric-intent.json)

Complete: False. Available matter reports: 4 / 4.

Checked real citations in available reports: 2296. Fictional by design (excluded): 70. Pending checks: 0.

Problem rate: 3.2% (73 / 2296) among recorded citations; coverage incomplete.

Final statuses for completed real-citation checks only:

| Status | Count |
|---|---|
| VERIFIED | 1867 |
| VERIFIED_MINOR_DEFECT | 117 |
| NOT_FOUND_LIKELY_FABRICATED | 0 |
| CITATION_POINTS_TO_DIFFERENT_CASE | 0 |
| MISCHARACTERIZED | 47 |
| MISQUOTED | 5 |
| WRONG_CITATION_REAL_CASE | 21 |
| UNABLE_TO_VERIFY | 239 |

## lrb-certiorari-quasi-judicial-land-use

Model: Claude Opus 5.5; reasoning effort: high.

Worker counting unit: citation occurrence in each unique matter document, separate prompt and rubric occurrences

Files read (worker reported):

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/instruction.md
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/tests/fixtures/rubric.json
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-2/instruction.md
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-2/tests/fixtures/rubric.json
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-orderpdf.docx
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-petition.docx
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-resolution.docx
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/workdir/attachments/1774361815-lcu-project.pdf

Coverage limits:

- Both assignments carry the same four attachments (byte-identical conversions), so each attachment is counted once. Assignment 2's input repeats the assignment-1 prompt; only each assignment's own current prompt is counted.
- The Order (orderpdf.docx) is six scanned page images with no text layer; the packet conversion contains only image tags. All six pages were read visually from the images embedded in the pinned original DOCX (no OCR). The service list on page 6 (email addresses) is not reproduced.
- The LCU Project PDF has no text layer beyond browser headers; its five pages were rendered and read visually. It contains no legal citations.
- The Petition's 28 embedded images (maps, charts, photos, a deed cover page, FAA figure, tax-roll screenshots) were reviewed at contact-sheet scale; the fine-print notes on images 14, 16, 25 and 26 were not legible and were not read. Images 11-12 reproduce FAA AC Figure 1 and were checked.
- The Resolution is OCR-derived text with garbles (e.g., '34-41 1' for 34-411, '10-41 8' for 10-418, '50-17.05' for 5J-17.05); several pin cites sit in inline images, which were read (image 7 '(h).', image 9 '34-377('). Recorded-instrument references (ORB/ORI numbers) in the legal description and plan are not treated as legal authority.
- Record citations to non-law sources (Petition.docx pages, LCU Project.pdf pages, the Lee County DCD application web page, the Florida courts jurisdiction map, transcripts, staff reports, the 2017 Biological Opinion, the SFWMD water supply plan, the Kingston settlement instrument) are not counted. Rubric citations to the Order ('Order.docx at N') are counted as citations to the circuit court's order and checked against its page images.
- Generic references with no identifiable provision (e.g., 'Florida's Sunshine Law', 'the Land Development Code', 'Federal regulations') are not counted separately; authorities embedded in quoted text (LDC s. 34-1102's list, s. 333.02's cross-reference, the Biological Opinion's 50 CFR 402.16 and CWA s. 404, the AC's ESA s. 7) are counted once per quoted block.
- The supplemental source pass attempted all 32 assigned occurrences. Nine FAA circular references now have substantive source reads, rather than index-only identification. For AC 150/5300-13A the accessible text is the 2014 Change 1 consolidation, not the unamended 2012 issue.
- Historical Lee County code requirements were checked where dated ordinance redlines or compilations supplied the relevant language. A complete January 2024 code/Lee Plan compilation was not recovered. Two historical code subsections and seven compound Lee Plan references remain unverified, along with the Babcock book and Mandelker/Tarlock article. Each row retains the retrieval attempts and any current-text comparison without calling that historical verification.
- All original 27 problem claims and five later claims received independent second review. The Smith article and Jennings characterization claims were downgraded to minor; four duplicate proposals in the later source pass retain their already completed independent rulings. The original first-pass and coverage-only judgments remain in the row history.
- Admin. Code AC-2-6 was read in its August 2022 version, not its 2019-20 version. Fine print in four Petition images remains unreadable, so the citation census is not asserted complete. Unread or inaccessible authority is UNABLE_TO_VERIFY, not evidence of fabrication.
- Current recorded coverage: 230 real-authority occurrences, including 11 UNABLE_TO_VERIFY. Status totals are derived from the saved per-reference judgments; historical aggregate statements above do not control current counts.

[Full citation evidence](results/lrb-certiorari-quasi-judicial-land-use.md)

## lrb-dcca-challenge-police-discipline

Model: Claude Opus 5.5; reasoning effort: high.

Worker counting unit: citation occurrence in each unique matter document, separate prompt and rubric occurrences

Files read (worker reported):

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-1/instruction.md
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-1/tests/fixtures/rubric.json
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-2/instruction.md
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-2/tests/fixtures/rubric.json
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-3/instruction.md
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-3/tests/fixtures/rubric.json
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-4/instruction.md
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-4/tests/fixtures/rubric.json
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-5/instruction.md
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-5/tests/fixtures/rubric.json
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-1/workdir/attachments/final_notice_adverse_action_braddock.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-1/workdir/attachments/comparator_discipline_cases.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-1/workdir/attachments/braddock_arbitration_award.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-2/workdir/attachments/douglas_v_veterans_admin.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-2/workdir/attachments/dcmr_title6b_1606.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-3/workdir/attachments/paperworkers_v_misco.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-3/workdir/attachments/wr_grace_v_rubber_workers.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-3/workdir/attachments/dc_code_1-605.02.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-3/workdir/attachments/fop_doc_labor_comm_v_perb_2009.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-3/workdir/attachments/perb_decision_braddock.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-4/workdir/attachments/supplemental_comparator_disclosure.pdf

Coverage limits:

- Douglas v. Veterans Administration attachment (34 PDF pages) is an OCR text layer of the MSPB-reporter print (5 MSPB 313-346); all 34 pages have extracted text and were read, but OCR garbles some names, numbers and footnote markers (e.g. '0PM', 'Lwtta', 'Bmzzotie', '8%', footnote 1 'Title 6'). Citations are recorded as written in the OCR text, and statuses note when a defect may be an OCR artifact rather than an error in the original.
- W.R. Grace and Misco attachments are Justia web prints (one PDF page of opinion text each, plus navigation pages); locations use the embedded 'Page 461 U.S. ...'/'Page 484 U.S. ...' markers. Justia artifacts were compared with the official texts on CourtListener: Misco p.42 'W. R. Grace ..., 461 U. S. 757, 334 U. S. 766', Misco n.10 '415 F.2d 186', Misco p.35 '(CA5 1986)', Grace p.765 page-marker garble ('4 and S. 765') and n.1 'W. P. Grace' (record cite, not counted).
- FOP v. PERB attachment is a FindLaw web print (14 PDF pages, pages 8-14 are site boilerplate with no opinion text); compared against the official opinion text on CourtListener.
- D.C. Code attachment is a 2026 web print of the official code site; navigation links (§§ 1-605.01, 1-605.03) and site publication metadata (Law 26-140, Act 26-357, Public Law 115-334) were not counted as citations.
- Prompts were counted from each assignment's own prompt text (input.json 'prompt'); instruction.md for assignments 2-5 repeats earlier prompts and those repetitions were not counted again. Rubric fields were counted per criterion: authorities named in the criterion text and each authority in the source field. Justification fields quote the prompt and add no authority of their own; those quotations were not counted again.
- The two scenario memoranda (comparator_discipline_cases.pdf; supplemental_comparator_disclosure.pdf) are record evidence; their citation in rubric source fields was not counted. Fictional-by-design records are the scenario adjudications (Final Notice, Award, PERB Opinion No. 1904) and scenario disciplinary case numbers.
- The second census added 159 internal Chapter 16 cross-references and statutory short forms omitted initially. It did not independently rescan every original occurrence, so the overall census remains incomplete. Navigation metadata and non-authority record references remain excluded as described above.
- All 436 supplemental source-reading assignments received retrieval attempts: 372 initially unread occurrences in three batches, plus 64 added by the second census. Row histories preserve the initial unattempted judgments and later actual reads. Remaining unverified sources include historical agency and Civil Service Commission decisions, personnel manuals, legislative materials, secondary works, unavailable reporter pinpoints, and an October 2019 D.C. Register notice; each affected row records the specific attempts and limits.
- All initial and later problem proposals received independent second review. Proposed Dennison, Bowman and Cafferello defects based on auditor summary labels were rejected; the source-reading proposals and reasons for rejection remain visible. Bowman and Cafferello cited_for labels were corrected with their initial labels retained.
- The Article 12 grievance reference conflicts with both real 2020–23 and 2023–26 agreements and current D.C. Code section 1-617.08(c), but arbitration under that article is shared across the fictional record. The citation discrepancy is not treated as a rubric defect or a reason to reject the scenario premise. No criterion was found to reward relying on that discrepancy.
- Current recorded coverage: 794 real-authority occurrences, including 123 UNABLE_TO_VERIFY. OCR-only and scan-margin defects are distinguished from errors in the original legal authority. No citator or exhaustive later-history review was performed.

[Full citation evidence](results/lrb-dcca-challenge-police-discipline.md)

## lrb-forum-non-conveniens-response

Model: Claude Opus 5.5; reasoning effort: high.

Worker counting unit: citation occurrence in each unique matter document, separate prompt and rubric occurrences

Files read (worker reported):

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/instruction.md
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/tests/fixtures/rubric.json
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-2/instruction.md
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-2/tests/fixtures/rubric.json
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Defendants%20Motion%20to%20Transfer.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Davis%20Complaint.docx
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/First%20Am%20Bank%20v.%20Guerine.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/Langenhorst%20v.%20Norfolk%20Southern.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/workdir/attachments/2023%20Annual%20Report%20Statistical%20Summary.pdf

Coverage limits:

- Attachment counting: the six attachments are identical in assignment-1 and assignment-2 packets apart from the source-URL line (verified by diff); each is counted once. Prompts and rubric fields are counted per assignment; assignment-2's copy of the prior assignment-1 prompt contains no citations.
- All text read is the repository's extraction of the pinned upstream files (no OCR). No attachment page was marked as lacking extracted text. The 303-page 2023 Annual Report is mostly numeric tables; 16 near-empty pages are section dividers or charts with little text, and chart/table layouts in the extraction scramble some row/column labels (affects one motion citation marked UNABLE_TO_VERIFY).
- The Davis Complaint is a DOCX conversion; original pagination is not retained, so complaint locations are by paragraph.
- The Langenhorst attachment runs from the majority's 'Affirmed.' directly into Justice Garman's dissent (PDF pp.12-20) without a dissent heading; dissent locations are labelled in this file.
- Pin-cite checks for Illinois Reports pages rely on page markers in CourtListener's Harvard CAP text (mapped with a constant per-opinion offset confirmed against several known pins); where no markers were available the proposition, not the page, was checked.
- Statutes and Supreme Court Rules were read in their current official versions (ILGA, illinoiscourts.gov compiled rules current to Oct. 16, 2026). Historical editions cited in the opinions (e.g. West 1992/2000, 134 Ill. 2d Rules) were not read; where numbering changed (Rule 306) this is flagged.
- The 2023 Annual Report attachment was checked only against itself (it is the cited document); it was not compared with the AOIC's published PDF.
- The assignment-1 prompt contains an uncited legal assertion (venue in wrongful death proper where any part of the action occurred, including the place of death); with no authority named or quoted it is not counted. The assignment-2 prompt's sentence is counted because it quotes Langenhorst's language verbatim.
- Embedded pin cites to Dawdy (76) and Guerine (44) inside Langenhorst were checked by reading those opinions with Illinois Reports page markers; each record carries a page-specific excerpt.
- Embedded citations in the three supplied opinions were checked for identity via CourtListener citation lookup and, for propositions, by reading the cited passage on CourtListener; supplied opinion texts were themselves compared with CourtListener's official text at sampled passages (matching).
- No upstream scripts were run, and no paid APIs were used. CourtListener was reached through its connector. ILGA pages were fetched directly; the site's TLS chain needed the published Sectigo intermediate certificate, and verification was not disabled.
- The original exclusion of bare case-name references was corrected by a complete supplemental scan of readable text. It adds 97 named-authority short forms, all checked against judicial text; the first second-review worker's eleven additions are included exactly once. Primary-source access and extraction limits remain as stated.
- Counting includes named-authority short forms after the supplemental census; the initial bare-name exclusion is superseded. Repeated attachment copies and non-authority record references are excluded.
- All 63 initially unverified occurrences received retrieval attempts. Independent review retained the Ferris wrong-citation claim and treated five challenged supervisory-order parentheticals as minor defects; all nine supplemental proposals have saved second judgments and rubric-intent records.
- Remaining unverified occurrences concern Restatement section 84 comment c, the Maag/Kitch/Sunderland articles, historical Rule 306, and the truncated Lawson and Eby supervisory orders. The per-reference attempts specify what was unavailable. Historical rule versions beyond those actually read remain a limit.
- Current recorded coverage: 663 real-authority occurrences, including 10 UNABLE_TO_VERIFY. Status totals are derived from the saved per-reference judgments; historical aggregate statements above do not control current counts.

[Full citation evidence](results/lrb-forum-non-conveniens-response.md)

## lrb-vicar-trial-jury-instructions

Model: Claude Opus 5.5; reasoning effort: high.

Worker counting unit: citation occurrence in each unique matter document, separate prompt and rubric occurrences

Files read (worker reported):

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/instruction.md
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/tests/fixtures/rubric.json
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Facts.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White%20Horse.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/702.11.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/704.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/706.1.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/707.11.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/708.6.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton%20State%20Plea.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf
- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Facts.pdf

Coverage limits:

- Unique documents: 12 attachments plus 2 prompts and 2 rubrics. The assignment 2 packet reprints the assignment 1 prompt and all assignment 1 attachments; those were counted once, under assignment 1. Assignment 2's Facts.pdf is byte-identical in extracted text to assignment 1's Facts.pdf except for its source line, so it was read and counted once.
- Patton State Plea.pdf (6 pages) has no text layer; the supplied extraction contains only the e-filing stamp on each page. The PDF was downloaded from the pinned Hugging Face revision and its page images were read visually. Every page, including the signature pages (3 and 6), was read; citations were transcribed by eye, with no OCR.
- The five opinion attachments (Poe, White Horse, Kehoe, Ellison, Kuhse) were compared word-for-word with the official court PDFs (Eighth Circuit opinion directory; Iowa Judicial Branch). Each was identical apart from the packet's source header. Citation errors inside those opinions are therefore the courts' own (environment-only), not packet corruption.
- The five Iowa Code attachments are 'Iowa Code 2026' prints, although the prompt cites the 2020 Code. Each was compared with the official 2020 edition: chapter 704 and §§ 706.1, 707.11, and 708.6 are identical in text, while § 702.11(2)(c)-(f) differs (subsection 1, the part cited in the rubric, is identical). Cross-references inside the 2026 prints were checked against 2026 sections.
- Facts.pdf contains no citations to legal authority. Its case-record references (about 97 trial-transcript 'TT' cites, about 32 'R. Doc.' cites, 'Id.' record short forms, and the M./P./G. Br. abbreviation key) are references to the scenario case record, not legal authority, and are excluded. Following the sibling matters' convention for scenario record documents, the 24 prompt and rubric references to Facts.pdf and Patton State Plea.pdf (document lists and rubric source fields) are included as fictional_by_design entries (authority_type 'other') and were not checked. The plea petitions look like real Polk County filings and Facts.pdf reads like a real government brief, so 'fictional_by_design' here means 'scenario record, not legal authority'. Whether the prosecution is real was not investigated. No fictional legal authority (an invented case, statute, or rule) was found.
- Authority types follow the sibling and Harvey vocabulary: U.S. and Iowa constitutional provisions are typed 'statute'; law-review articles and the Model Penal Code are typed 'restatement_or_treatise'; the Iowa model jury instruction is typed 'other'.
- Counting conventions: each explicit citation string counts once, including short forms and Id./id. (resolved to the antecedent in citation_as_written brackets). Statutory section mentions given by number count once each. Bare case names count when invoked as authority ('In Stover, we held', 'Under Aguilar', 'Strickland prejudice') but not when incidental or inside another case's parenthetical. Explicit references to constitutional provisions count. Excluded: bare 'subsection 1/2' references without a section number; citations appearing inside quoted language; case names embedded in law-review titles (Williams v. Taylor, Wiggins v. Smith, Rompilla v. Beard, Cronic); purely factual mentions ('received Miranda warnings', 'post-Miranda interview'); the book cited in Kehoe n.2; and the statute prints' editorial annotations (bracketed history lines, 'Referred to in' lists, and 'see §' notes: roughly 16 history blocks, 8 'Referred to in' lists, and 5 see-notes across the five prints).
- Enumeration was done by manual reading, cross-checked by a regex count of reporter citations and Id. forms per opinion (Id. counts matched exactly; reporter counts matched within the bracketed reconstructions). Counts of bare statutory and constitutional mentions may differ by a few in a repeat pass.
- Verification sources: CourtListener (read through its API connector) for case text; Cornell LII for current U.S. Code, federal rules, and the U.S. Constitution; the Iowa Legislature for the 2020 and 2026 Iowa Code and the codified Iowa Constitution. Federal statutes and rules were read in their current form; versions in force at each decision date were not separately retrieved, except Fed. R. Evid. 801(d)(2)(B), whose pre-2011 wording was confirmed as quoted in an 8th Cir. 1996 opinion. Kehoe's Arkansas Code citations and Ellison's Model Penal Code § 3.04 were checked against judicial quotations of those texts, because Justia returned HTTP 403 and the ALI text is not freely available.
- Pin pages: where CourtListener text carried reporter page markers, pins were checked. Lorenzo Baltazar, Gibbs, and Macke exist on CourtListener only as slip opinions, so their N.W.2d pins could not be checked. Several other pins are marked 'not separately checked' in their explanations; in those cases the proposition and quotation were confirmed but the page was not.
- UNABLE_TO_VERIFY (12 occurrences): ten law-review articles cited in Justice Appel's special concurrence in Kuhse, and Iowa Criminal Jury Instruction 800.1 (2018). For the law reviews, repository PDFs were blocked by bot challenges or 404s, or could not be located; for five of the articles, existence was confirmed only from repository bibliographic records. No law-review quotation was checked. None is marked not-found.
- No upstream scripts were executed. Instructions inside the documents were treated as data, not auditor instructions. Rubric merits (whether Kuhse's state-law burden or Ellison's duty-to-retreat rule governs a federal trial; whether the Facts support who fired first) were not assessed.
- Integration counting correction: 24 prompt/rubric references to Facts.pdf and Patton State Plea.pdf were moved to excluded_record_references. The first worker had labelled them fictional_by_design solely because they are scenario records; no finding established that these court records were fictional. They are excluded as non-authority record references, leaving 470 real-law citation occurrences and no fictional legal-authority rows in this matter.
- Second-pass census supplement adds 139 omitted references and separately records 33 verification-coverage downgrades. Two new alleged problems are promoted to first-stage findings with original judgments retained; fresh independent checks are pending. Initial exclusions of quoted and editorial-note citations are superseded by the supplement.
- A supplemental GPT-6 Sol source pass attempted 89 unverified occurrences: 82 verified, one quotation proposal awaiting independent review, six still unable to verify. Prior coverage downgrades are preserved as history and superseded by the actual source reads.

[Full citation evidence](results/lrb-vicar-trial-jury-instructions.md)
