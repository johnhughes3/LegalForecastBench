# Citation checks: lrb-vicar-trial-jury-instructions

AI-generated citation checks, not human legal verification or score corrections. The counting unit is a citation in a unique matter document, not each repeated assignment packet. Worker file lists and limits are reproduced below; absence of a stated limit does not independently establish exhaustive coverage. Completion requires an explicit census-complete judgment; verification limits remain visible. Every first-check problem requires an independent second check, including overturned findings. Missing files and pending checks never establish a zero-problem result.

Model: Claude Opus 5.5; reasoning effort: high.

Worker coverage: {'files_read': ['https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/instruction.md', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/tests/fixtures/rubric.json', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Facts.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White%20Horse.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/702.11.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/704.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/706.1.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/707.11.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/708.6.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton%20State%20Plea.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf', 'https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Facts.pdf'], 'limits': ["Unique documents: 12 attachments plus 2 prompts and 2 rubrics. The assignment 2 packet reprints the assignment 1 prompt and all assignment 1 attachments; those were counted once, under assignment 1. Assignment 2's Facts.pdf is byte-identical in extracted text to assignment 1's Facts.pdf except for its source line, so it was read and counted once.", 'Patton State Plea.pdf (6 pages) has no text layer; the supplied extraction contains only the e-filing stamp on each page. The PDF was downloaded from the pinned Hugging Face revision and its page images were read visually. Every page, including the signature pages (3 and 6), was read; citations were transcribed by eye, with no OCR.', "The five opinion attachments (Poe, White Horse, Kehoe, Ellison, Kuhse) were compared word-for-word with the official court PDFs (Eighth Circuit opinion directory; Iowa Judicial Branch). Each was identical apart from the packet's source header. Citation errors inside those opinions are therefore the courts' own (environment-only), not packet corruption.", "The five Iowa Code attachments are 'Iowa Code 2026' prints, although the prompt cites the 2020 Code. Each was compared with the official 2020 edition: chapter 704 and §§ 706.1, 707.11, and 708.6 are identical in text, while § 702.11(2)(c)-(f) differs (subsection 1, the part cited in the rubric, is identical). Cross-references inside the 2026 prints were checked against 2026 sections.", "Facts.pdf contains no citations to legal authority. Its case-record references (about 97 trial-transcript 'TT' cites, about 32 'R. Doc.' cites, 'Id.' record short forms, and the M./P./G. Br. abbreviation key) are references to the scenario case record, not legal authority, and are excluded. Rubric source fields that cite only Facts.pdf or Patton State Plea.pdf page numbers are record citations and are excluded too. No fictional legal authority was identified in the matter, so the census contains no fictional_by_design entries. The underlying prosecution appears to be a real case, but this was not investigated.", "Counting conventions: each explicit citation string counts once, including short forms and Id./id. (resolved to the antecedent in citation_as_written brackets). Statutory section mentions given by number count once each. Bare case names count when invoked as authority ('In Stover, we held', 'Under Aguilar', 'Strickland prejudice') but not when incidental or inside another case's parenthetical. Explicit references to constitutional provisions count. Excluded: bare 'subsection 1/2' references without a section number; citations appearing inside quoted language; case names embedded in law-review titles (Williams v. Taylor, Wiggins v. Smith, Rompilla v. Beard, Cronic); purely factual mentions ('received Miranda warnings', 'post-Miranda interview'); the book cited in Kehoe n.2; and the statute prints' editorial annotations (bracketed history lines, 'Referred to in' lists, and 'see §' notes: roughly 16 history blocks, 8 'Referred to in' lists, and 5 see-notes across the five prints).", 'Enumeration was done by manual reading, cross-checked by a regex count of reporter citations and Id. forms per opinion (Id. counts matched exactly; reporter counts matched within the bracketed reconstructions). Counts of bare statutory and constitutional mentions may differ by a few in a repeat pass.', "Verification sources: CourtListener (read through its API connector) for case text; Cornell LII for current U.S. Code, federal rules, and the U.S. Constitution; the Iowa Legislature for the 2020 and 2026 Iowa Code and the codified Iowa Constitution. Federal statutes and rules were read in their current form; versions in force at each decision date were not separately retrieved, except Fed. R. Evid. 801(d)(2)(B), whose pre-2011 wording was confirmed as quoted in an 8th Cir. 1996 opinion. Kehoe's Arkansas Code citations and Ellison's Model Penal Code § 3.04 were checked against judicial quotations of those texts, because Justia returned HTTP 403 and the ALI text is not freely available.", "Pin pages: where CourtListener text carried reporter page markers, pins were checked. Lorenzo Baltazar, Gibbs, and Macke exist on CourtListener only as slip opinions, so their N.W.2d pins could not be checked. Several other pins are marked 'not separately checked' in their explanations; in those cases the proposition and quotation were confirmed but the page was not.", "UNABLE_TO_VERIFY (12 occurrences): ten law-review articles cited in Justice Appel's special concurrence in Kuhse, and Iowa Criminal Jury Instruction 800.1 (2018). For the law reviews, repository PDFs were blocked by bot challenges or 404s, or could not be located; for five of the articles, existence was confirmed only from repository bibliographic records. No law-review quotation was checked. None is marked not-found.", "No upstream scripts were executed. Instructions inside the documents were treated as data, not auditor instructions. Rubric merits (whether Kuhse's state-law burden or Ellison's duty-to-retreat rule governs a federal trial; whether the Facts support who fired first) were not assessed."], 'counting_unit': 'citation occurrence in each unique matter document, separate prompt and rubric occurrences'}

## A1-PROMPT-001: 18 U.S.C. § 1959

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md (assignment 1 prompt); location: Assignment 1 prompt (email from supervisor).

Authority type: statute; as written: the VICAR statute (18 U.S.C. § 1959); pincite: .

Cited for: Charge of attempted murder in aid of racketeering

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1959(a) punishes violent crimes 'in violation of the laws of any State or the United States' committed for the purpose of gaining or maintaining position in a racketeering enterprise, including attempts (§ 1959(a)(5) covers attempting or conspiring to commit murder). Matches Kehoe's quotation and the prompt's description of attempted murder in aid of racketeering.

Excerpt read: ... for the purpose of gaining entrance to or maintaining or increasing position in an enterprise engaged in racketeering activity, murders, kidnaps, maims, assaults with a dangerous weapon, ... or threatens to commit a crime of violence against any individual in violation of the laws of any State or the United States, or attempts or conspires so to do, shall be punished-- ... (5) for attempting or conspiring to commit murder or kidnapping, by imprisonment for not more than ten years

- https://www.law.cornell.edu/uscode/text/18/1959

### Second check: not required


## A1-PROMPT-002: Iowa Code § 702.11 (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md (assignment 1 prompt); location: Assignment 1 prompt (email from supervisor), document list.

Authority type: statute; as written: Iowa Code § 702.11 (2020) (702.11.pdf); pincite: .

Cited for: Supplied authority

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

The prompt cites the 2020 Code but the supplied 702.11.pdf is the 2026 edition. Read both from the Iowa Legislature: subsection 1 (the forcible-felony definition) is identical, but subsection 2 differs between editions (2(c) 'subparagraph (3)' in 2020 vs '(2)' in 2026; 2(d) adds 'or adult providing training or instruction' in 2026; 2(e) 726.6 'subsection 6' vs '7'; 2(f) 708.2 'subsection 4' vs '5'; the 2026 history adds 2021 Acts ch. 102, § 4). The citation is correct; the supplied text is not the cited edition.

Excerpt read: 2020 and 2026: '1. A "forcible felony" is any felonious child endangerment, assault, murder, sexual abuse, kidnapping, robbery, human trafficking, arson in the first degree, or burglary in the first degree.' 2020: 'd. Sexual exploitation by a counselor, therapist, or school employee in violation of section 709.15.'

- https://www.legis.iowa.gov/docs/code/2020/702.11.pdf
- https://www.legis.iowa.gov/docs/code/2026/702.11.pdf

### Second check: not required


## A1-PROMPT-003: Iowa Code ch. 704 (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md (assignment 1 prompt); location: Assignment 1 prompt (email from supervisor), document list.

Authority type: statute; as written: Iowa Code ch. 704 (2020) (704.pdf); pincite: .

Cited for: Supplied authority

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 chapter 704. The supplied file is the 'Iowa Code 2026' print; compared word-for-word with the official 2020 edition, the text is identical apart from print-date lines and 'Referred to in' annotations.

Excerpt read: CHAPTER 704 FORCE -- REASONABLE OR DEADLY -- DEFENSES ... 704.1 Reasonable force ... 704.6 When defense not available.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## A1-PROMPT-004: Iowa Code § 706.1 (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md (assignment 1 prompt); location: Assignment 1 prompt (email from supervisor), document list.

Authority type: statute; as written: Iowa Code § 706.1 (2020) (706.1.pdf); pincite: .

Cited for: Supplied authority

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 text. The supplied file is the 'Iowa Code 2026' print; compared word-for-word with the official 2020 edition, the text is identical apart from print-date lines and 'Referred to in' annotations.

Excerpt read: 706.1 Conspiracy. 1. A person commits conspiracy with another if, with the intent to promote or facilitate the commission of a crime which is an aggravated misdemeanor or felony, the person does either of the following: a. Agrees with another that they or one or more of them will engage in conduct constituting the crime ...

- https://www.legis.iowa.gov/docs/code/2020/706.1.pdf

### Second check: not required


## A1-PROMPT-005: Iowa Code § 707.11 (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md (assignment 1 prompt); location: Assignment 1 prompt (email from supervisor), document list.

Authority type: statute; as written: Iowa Code § 707.11 (2020) (707.11.pdf); pincite: .

Cited for: Supplied authority

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 text. The supplied file is the 'Iowa Code 2026' print; compared word-for-word with the official 2020 edition, the text is identical apart from print-date lines and 'Referred to in' annotations.

Excerpt read: 707.11 Attempt to commit murder. 1. A person commits the offense of attempt to commit murder when, with the intent to cause the death of another person and not under circumstances which would justify the person's actions, ...

- https://www.legis.iowa.gov/docs/code/2020/707.11.pdf

### Second check: not required


## A1-PROMPT-006: Iowa Code § 708.6 (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md (assignment 1 prompt); location: Assignment 1 prompt (email from supervisor), document list.

Authority type: statute; as written: Iowa Code § 708.6 (2020) (708.6.pdf); pincite: .

Cited for: Supplied authority

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 text (defines intimidation with a dangerous weapon as shooting into an occupied vehicle with intent to injure or provoke fear). The supplied file is the 'Iowa Code 2026' print; compared word-for-word with the official 2020 edition, the text is identical apart from print-date lines and 'Referred to in' annotations. Whether § 708.6 is a 'forcible felony' under § 702.11 is not stated in either text.

Excerpt read: 1. A person commits a class "C" felony when the person, with the intent to injure or provoke fear or anger in another, shoots, throws, launches, or discharges a dangerous weapon at, into, or in a building, vehicle, ... occupied by another person

- https://www.legis.iowa.gov/docs/code/2020/708.6.pdf

### Second check: not required


## A1-PROMPT-007: State v. Ellison, No. 21-0657 (Iowa Feb. 3, 2023)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md (assignment 1 prompt); location: Assignment 1 prompt (email from supervisor), document list.

Authority type: case; as written: State v. Ellison, No. 21-0657, slip op. (Iowa Feb. 3, 2023) (Ellison.pdf); pincite: .

Cited for: Supplied authority

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Downloaded the official Iowa Supreme Court PDF (linked from CourtListener) and compared it word-for-word with the supplied Ellison.pdf text: identical apart from the source header. Docket number and filing date (Feb. 3, 2023) match the official opinion.

Excerpt read: IN THE SUPREME COURT OF IOWA No. 21-0657 Submitted September 15, 2022--Filed February 3, 2023 STATE OF IOWA, Appellee, vs. DEONTE WB ELLISON, Appellant.

- https://www.iowacourts.gov/courtcases/15974/embed/SupremeCourtOpinion
- https://www.courtlistener.com/opinion/9372742/state-of-iowa-v-deonte-wb-ellison/

### Second check: not required


## A1-PROMPT-008: United States v. Kehoe, No. 99-2897 (8th Cir. Nov. 8, 2002), reported at 310 F.3d 579

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md (assignment 1 prompt); location: Assignment 1 prompt (email from supervisor), document list.

Authority type: case; as written: United States v. Kehoe, No. 99-2897, slip op. (8th Cir. Nov. 8 2002) (Kehoe.pdf); pincite: .

Cited for: Supplied authority

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Downloaded the official Eighth Circuit slip opinion and compared it with the supplied Kehoe.pdf: word-identical apart from the source header. Docket number 99-2897 and filing date November 8, 2002 match the slip. (CourtListener dates its reporter-text cluster 2003-01-10.) The prompt's 'Nov. 8 2002' lacks a comma -- typographical only.

Excerpt read: No. 99-2897 ... Submitted: June 28, 2002 Filed: November 8, 2002 ... WOLLMAN, Circuit Judge.

- https://ecf.ca8.uscourts.gov/opndir/02/11/992897P.pdf
- https://www.courtlistener.com/opinion/779816/united-states-v-chevie-obrien-kehoe-also-known-as-jonathan-collins-also/

### Second check: not required


## A1-PROMPT-009: United States v. Poe, No. 05-2914 (8th Cir. Apr. 6, 2006), reported at 442 F.3d 1101

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md (assignment 1 prompt); location: Assignment 1 prompt (email from supervisor), document list.

Authority type: case; as written: United States v. Poe, No. 05-2914, slip op. (8th Cir. Apr. 6. 2006) (Poe.pdf); pincite: .

Cited for: Supplied authority

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Downloaded the official Eighth Circuit slip opinion and compared it with the supplied Poe.pdf: word-identical apart from the source header. Docket and date match. The prompt's 'Apr. 6. 2006' has a stray period -- typographical only.

Excerpt read: No. 05-2914 ... Submitted: January 11, 2006 Filed: April 6, 2006 ... JOHN R. GIBSON, Circuit Judge.

- https://ecf.ca8.uscourts.gov/opndir/06/04/052914P.pdf
- https://www.courtlistener.com/opinion/793839/united-states-v-tommy-lee-poe/

### Second check: not required


## A1-PROMPT-010: United States v. White Horse, No. 21-2871 (8th Cir. June 3, 2022), reported at 35 F.4th 1119

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md (assignment 1 prompt); location: Assignment 1 prompt (email from supervisor), document list.

Authority type: case; as written: United States v. White Horse, No. 21-2871, slip op. (8th Cir. June 3, 2022) (White Horse.pdf); pincite: .

Cited for: Supplied authority

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Downloaded the official Eighth Circuit slip opinion and compared it with the supplied White Horse.pdf: word-identical apart from the source header. Docket and date match.

Excerpt read: No. 21-2871 ... Submitted: March 16, 2022 Filed: June 3, 2022 ... GRUENDER, Circuit Judge.

- https://ecf.ca8.uscourts.gov/opndir/22/06/212871P.pdf
- https://www.courtlistener.com/opinion/6474645/united-states-v-samuel-white-horse/

### Second check: not required


## A1-RUBRIC-001: United States v. Poe, No. 05-2914, slip op. at 3 (8th Cir. Apr. 6, 2006)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_1 (+5), source field.

Authority type: case; as written: United States v. Poe, No. 05-2914, slip op. at 3 (8th Cir. Apr. 6. 2006) (Poe.pdf); pincite: 3.

Cited for: Refusal of justification instruction reviewed de novo

Quotes: ['Whether there is sufficient evidence to support the submission of an instruction on an affirmative defense is a question of law which we review de novo.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official slip (word-identical to the supplied Poe.pdf): page 3 contains the quoted sentence verbatim, which Poe attributes to Hudson, 414 F.3d at 933 (also verified). Supports de novo review of whether evidence suffices to submit an affirmative-defense instruction.

Excerpt read: Whether there is sufficient evidence to support the submission of an instruction on an affirmative defense is a question of law which we review de novo. United States v. Hudson, 414 F.3d 931, 933 (8th Cir. 2005).

- https://ecf.ca8.uscourts.gov/opndir/06/04/052914P.pdf

### Second check: not required


## A1-RUBRIC-002: United States v. White Horse, No. 21-2871, slip op. at 2-3 (8th Cir. June 3, 2022)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_2 (-30 penalty), source field.

Authority type: case; as written: United States v. White Horse, No. 21-2871, slip op. at 2-3 (8th Cir. June 3, 2022) (White Horse.pdf); pincite: 2-3.

Cited for: Abuse-of-discretion review of instructions generally (source for penalized statement)

Quotes: ['review[s] jury instructions for an abuse of discretion']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official slip: at 2 the court states 'We review jury instructions for an abuse of discretion' (citing Williams) and at 3 continues with the broad-discretion and 'fairly and adequately' language, in the context of an instruction's wording (omitted element), not sufficiency of evidence for an affirmative-defense instruction. The rubric's quotation and parenthetical characterization are accurate.

Excerpt read: We review jury instructions for an abuse of discretion. United States v. Williams, 605 F.3d 556, 567 (8th Cir. 2010). "A district court has broad discretion in instructing the jury, and jury instructions do not need to be technically perfect or even a model of clarity."

- https://ecf.ca8.uscourts.gov/opndir/22/06/212871P.pdf

### Second check: not required


## A1-RUBRIC-003: United States v. Kehoe, No. 99-2897, slip op. at 10 (8th Cir. Nov. 8, 2002)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_3 (+5), source field.

Authority type: case; as written: United States v. Kehoe, No. 99-2897, slip op. at 10 (8th Cir. Nov. 8 2002) (Kehoe.pdf); pincite: 10.

Cited for: VICAR predicate offense can come from state law

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official slip: page 10 quotes § 1959(a) ('in violation of the laws of any State or the United States') and states that conduct violating a state or federal criminal law is a requisite element of a § 1959 violation, rejecting a Tenth Amendment challenge to a § 1959 conviction resting on Arkansas murder law. Supports the proposition that a VICAR predicate can come from state law.

Excerpt read: RICO explicitly provides that conduct that violates a state or federal criminal law is a requisite element of a § 1959 violation.

- https://ecf.ca8.uscourts.gov/opndir/02/11/992897P.pdf

### Second check: not required


## A1-RUBRIC-004: Iowa Code § 707.11(1) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_5 (+5), source field.

Authority type: statute; as written: Iowa Code § 707.11(1) (2020) (707.11.pdf); pincite: (1).

Cited for: Justification is a defense to Iowa attempted murder

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; the offense is defined to exclude 'circumstances which would justify the person's actions', so justification is a defense to attempted murder.

Excerpt read: with the intent to cause the death of another person and not under circumstances which would justify the person's actions, the person does any act by which the person expects to set in motion a force or chain of events which will cause or result in the death of the other person.

- https://www.legis.iowa.gov/docs/code/2020/707.11.pdf

### Second check: not required


## A1-RUBRIC-005: State v. Ellison, No. 21-0657, slip op. at 8 (Iowa Feb. 3, 2023)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_7 (+5), source field.

Authority type: case; as written: State v. Ellison, No. 21-0657, slip op. at 8 (Iowa Feb. 3, 2023) (Ellison.pdf); pincite: 8.

Cited for: Person engaged in illegal activity has a duty to retreat

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official opinion (identical to the supplied file): page 8 explains, via Lorenzo Baltazar, that § 704.1(3) by implication continues a duty to retreat for a person engaged in illegal activity. Supports the rule cited for; whether Patton was engaged in illegal activity is a factual application, not a citation question.

Excerpt read: we went on to say that the new language by implication continued to impose a duty to retreat if a person is engaging in illegal activity or not lawfully present. ... The usual duty to retreat generally still exists if a person is engaged in illegal activity or has no right to be present.

- https://www.iowacourts.gov/courtcases/15974/embed/SupremeCourtOpinion

### Second check: not required


## A1-RUBRIC-006: Iowa Code § 704.1(3) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_7 (+5), source field.

Authority type: statute; as written: Iowa Code ch. 704, § 704.1(3)(2020) (704.pdf); pincite: (3).

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (unchanged since 2017 Iowa Acts ch. 69, § 37, per the history note). By negative implication a person engaged in illegal activity has a duty to retreat, as Ellison (at 8) and Lorenzo Baltazar hold; the subsection itself states only the no-duty rule for persons not engaged in illegal activity.

Excerpt read: 3. A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force as specified in this chapter. ... 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## A1-RUBRIC-007: State v. Ellison, No. 21-0657, slip op. at 8 (Iowa Feb. 3, 2023)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_9 (+5), source field.

Authority type: case; as written: State v. Ellison, No. 21-0657, slip op. at 8 (Iowa Feb. 3, 2023) (Ellison.pdf); pincite: 8.

Cited for: Patton had a duty to retreat before using deadly force

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official opinion (identical to the supplied file): page 8 explains, via Lorenzo Baltazar, that § 704.1(3) by implication continues a duty to retreat for a person engaged in illegal activity. Supports the rule cited for; whether Patton was engaged in illegal activity is a factual application, not a citation question.

Excerpt read: we went on to say that the new language by implication continued to impose a duty to retreat if a person is engaging in illegal activity or not lawfully present. ... The usual duty to retreat generally still exists if a person is engaged in illegal activity or has no right to be present.

- https://www.iowacourts.gov/courtcases/15974/embed/SupremeCourtOpinion

### Second check: not required


## A1-RUBRIC-008: Iowa Code § 704.1(3) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_9 (+5), source field.

Authority type: statute; as written: Iowa Code ch. 704 § 704.1(3) (2020) (704.pdf); pincite: (3).

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (unchanged since 2017 Iowa Acts ch. 69, § 37, per the history note). By negative implication a person engaged in illegal activity has a duty to retreat, as Ellison (at 8) and Lorenzo Baltazar hold; the subsection itself states only the no-duty rule for persons not engaged in illegal activity.

Excerpt read: 3. A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force as specified in this chapter. ... 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## A1-RUBRIC-009: Iowa Code § 704.6(3) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_15 (+10), source field.

Authority type: statute; as written: Iowa Code ch. 704 § 704.6(3) (2020) (704.pdf); pincite: (3).

Cited for: Patton's shooting was not justified self-defense (provocation by unlawful acts)

Quotes: ["The defense of justification is not available to . . . [o]ne who initially provokes the use of force against oneself by one's unlawful acts . . . ."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; the rubric's ellipsis quotation matches subsection 3, which is subject to the (a) gross-disproportion and (b) withdrawal exceptions that the quotation's closing ellipsis omits.

Excerpt read: 3. One who initially provokes the use of force against oneself by one's unlawful acts, unless: a. Such force is grossly disproportionate to the provocation ... or b. The person withdraws from physical contact with the other and indicates clearly to the other that the person desires to terminate the conflict but the other continues or resumes the use of force.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## A1-RUBRIC-010: Iowa Code § 704.6(1) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_17 (+5), source field.

Authority type: statute; as written: Iowa Code ch. 704, § 704.6(1) (2020) (704.pdf); pincite: (1).

Cited for: No justification for one participating in a forcible felony

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; justification is not available to one participating in a forcible felony.

Excerpt read: 1. One who is participating in a forcible felony, or riot, or a duel.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## A1-RUBRIC-011: Iowa Code § 702.11(1) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_18 (+5), source field.

Authority type: statute; as written: Iowa Code § 702.11(1) (2020) (702.11.pdf); pincite: (1).

Cited for: Forcible felony includes felonious assault

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 text: a forcible felony includes any felonious assault. Subsection 1 is identical in the 2026 print supplied.

Excerpt read: 1. A "forcible felony" is any felonious child endangerment, assault, murder, sexual abuse, kidnapping, robbery, human trafficking, arson in the first degree, or burglary in the first degree.

- https://www.legis.iowa.gov/docs/code/2020/702.11.pdf

### Second check: not required


## A1-RUBRIC-012: Iowa Code § 708.6 (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_28 (-20 penalty), source field.

Authority type: statute; as written: Iowa Code § 708.6 (2020) (708.6.pdf); pincite: .

Cited for: Crime of intimidation with a dangerous weapon (source for penalized statement)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 text (defines intimidation with a dangerous weapon as shooting into an occupied vehicle with intent to injure or provoke fear). The supplied file is the 'Iowa Code 2026' print; compared word-for-word with the official 2020 edition, the text is identical apart from print-date lines and 'Referred to in' annotations. Whether § 708.6 is a 'forcible felony' under § 702.11 is not stated in either text.

Excerpt read: 1. A person commits a class "C" felony when the person, with the intent to injure or provoke fear or anger in another, shoots, throws, launches, or discharges a dangerous weapon at, into, or in a building, vehicle, ... occupied by another person

- https://www.legis.iowa.gov/docs/code/2020/708.6.pdf

### Second check: not required


## A1-RUBRIC-013: Iowa Code § 704.6(1) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_29 (-10 penalty), source field.

Authority type: statute; as written: Iowa Code ch. 704, § 704.6(1) (2020) (704.pdf); pincite: (1).

Cited for: Legal basis of penalized statement that intimidation precludes justification

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text. Cited in a penalty criterion as the basis of the argument the rubric penalizes; § 704.6(1) bars justification for one participating in a forcible felony, and neither it nor § 702.11 states whether § 708.6 intimidation is a forcible felony. The citation accurately identifies the provision the penalized argument would rely on.

Excerpt read: 1. One who is participating in a forcible felony, or riot, or a duel.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## A1-RUBRIC-014: Iowa Code § 708.6 (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_29 (-10 penalty), source field.

Authority type: statute; as written: Iowa Code § 708.6 (2020) (708.6.pdf); pincite: .

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 text (defines intimidation with a dangerous weapon as shooting into an occupied vehicle with intent to injure or provoke fear). The supplied file is the 'Iowa Code 2026' print; compared word-for-word with the official 2020 edition, the text is identical apart from print-date lines and 'Referred to in' annotations. Whether § 708.6 is a 'forcible felony' under § 702.11 is not stated in either text.

Excerpt read: 1. A person commits a class "C" felony when the person, with the intent to injure or provoke fear or anger in another, shoots, throws, launches, or discharges a dangerous weapon at, into, or in a building, vehicle, ... occupied by another person

- https://www.legis.iowa.gov/docs/code/2020/708.6.pdf

### Second check: not required


## A1-RUBRIC-015: Iowa Code § 706.1(1) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_20 (+10), source field.

Authority type: statute; as written: Iowa Code ch. 706, § 706.1(1) (2020) (706.1.pdf); pincite: (1).

Cited for: Patton's admitted planning with others constitutes conspiracy

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; an agreement to engage in conduct constituting a felony (e.g., planning a shooting) is conspiracy, supporting the rubric's use alongside the plea admission.

Excerpt read: a. Agrees with another that they or one or more of them will engage in conduct constituting the crime or an attempt or solicitation to commit the crime. b. Agrees to aid another in the planning or commission of the crime

- https://www.legis.iowa.gov/docs/code/2020/706.1.pdf

### Second check: not required


## A1-RUBRIC-016: Iowa Code § 704.6(1) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_21 (+15), source field.

Authority type: statute; as written: Iowa Code ch. 704, § 704.6(1) (2020) (704.pdf); pincite: (1).

Cited for: Commission of conspiracy to commit a forcible felony precludes justification

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read official 2020 §§ 704.6(1), 706.1(1), 706.3 and 702.11. § 704.6(1) denies justification to 'one who is participating in a forcible felony'; conspiracy is not among the offenses listed in § 702.11(1), and § 706.3 treats conspiracy to commit a forcible felony as its own class C offense. The cited text therefore does not itself say that committing conspiracy precludes justification; the proposition holds only on the reading that the planned shooting (a felonious assault) is the forcible felony in which Patton participated. No case applying § 704.6(1) to conspiracy was found in a short CourtListener search. Loose fit between authority and the rubric's stated proposition.

Excerpt read: 1. One who is participating in a forcible felony, or riot, or a duel.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## A1-RUBRIC-017: Iowa Code § 706.1(1) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_21 (+15), source field.

Authority type: statute; as written: Iowa Code ch. 706, § 706.1(1) (2020) (706.1.pdf); pincite: (1).

Cited for: Same (defines conspiracy)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; an agreement to engage in conduct constituting a felony (e.g., planning a shooting) is conspiracy, supporting the rubric's use alongside the plea admission.

Excerpt read: a. Agrees with another that they or one or more of them will engage in conduct constituting the crime or an attempt or solicitation to commit the crime. b. Agrees to aid another in the planning or commission of the crime

- https://www.legis.iowa.gov/docs/code/2020/706.1.pdf

### Second check: not required


## A1-RUBRIC-018: Iowa Code § 704.3 (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_25 (-20 penalty), source field.

Authority type: statute; as written: Iowa Code ch. 704, § 704.3 (2020) (704.pdf); pincite: .

Cited for: Reasonable belief that deadly force was necessary (source for penalized statement)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; matches Ellison's quotation and the reasonable-belief element cited in the rubric.

Excerpt read: 704.3 Defense of self or another. A person is justified in the use of reasonable force when the person reasonably believes that such force is necessary to defend oneself or another from any actual or imminent use of unlawful force.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## A1-RUBRIC-019: Iowa Code § 704.6(1) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_27 (-20 penalty), source field.

Authority type: statute; as written: Iowa Code ch. 704, § 704.6(1) (2020) (704.pdf); pincite: (1).

Cited for: Reasonable belief of an imminent unlawful threat (source for penalized statement)

Quotes: []

Context: 

Fictional by design: False; 

### First check: MISCHARACTERIZED

Read official 2020 chapter 704. § 704.6(1) says only that justification is unavailable to one 'participating in a forcible felony, or riot, or a duel'; it says nothing about a reasonable belief in an imminent unlawful threat. That element is in § 704.3 ('reasonably believes that such force is necessary to defend oneself or another from any actual or imminent use of unlawful force'), which the parallel criterion_25 cites. The subsection cited does not support the proposition the criterion attaches to it.

Excerpt read: 1. One who is participating in a forcible felony, or riot, or a duel.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: pending


## A1-RUBRIC-020: United States v. White Horse, No. 21-2871, slip op. at 2-3 (8th Cir. June 3, 2022)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_26 (-30 penalty), source field.

Authority type: case; as written: United States v. White Horse, No. 21-2871, slip op. at 2-3 (8th Cir. June 3, 2022) (White Horse.pdf); pincite: 2-3.

Cited for: Speaks to instructions generally, not sufficiency for affirmative-defense instruction

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official slip: at 2 the court states 'We review jury instructions for an abuse of discretion' (citing Williams) and at 3 continues with the broad-discretion and 'fairly and adequately' language, in the context of an instruction's wording (omitted element), not sufficiency of evidence for an affirmative-defense instruction. The rubric's quotation and parenthetical characterization are accurate.

Excerpt read: We review jury instructions for an abuse of discretion. United States v. Williams, 605 F.3d 556, 567 (8th Cir. 2010). "A district court has broad discretion in instructing the jury, and jury instructions do not need to be technically perfect or even a model of clarity."

- https://ecf.ca8.uscourts.gov/opndir/22/06/212871P.pdf

### Second check: not required


## A1-RUBRIC-021: United States v. Poe, No. 05-2914, slip op. at 3 (8th Cir. Apr. 6, 2006)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/tests/fixtures/rubric.json (assignment 1 rubric); location: Assignment 1 rubric, criterion_26 (-30 penalty), source field.

Authority type: case; as written: United States v. Poe, No. 05-2914, slip op. at 3 (8th Cir. Apr. 6. 2006) (Poe.pdf); pincite: 3.

Cited for: Sufficiency for affirmative-defense instruction is a question of law

Quotes: ['Whether there is sufficient evidence to support the submission of an instruction on an affirmative defense is a question of law']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official slip (word-identical to the supplied Poe.pdf): page 3 contains the quoted sentence verbatim, which Poe attributes to Hudson, 414 F.3d at 933 (also verified). Supports de novo review of whether evidence suffices to submit an affirmative-defense instruction.

Excerpt read: Whether there is sufficient evidence to support the submission of an instruction on an affirmative defense is a question of law which we review de novo. United States v. Hudson, 414 F.3d 931, 933 (8th Cir. 2005).

- https://ecf.ca8.uscourts.gov/opndir/06/04/052914P.pdf

### Second check: not required


## A2-PROMPT-001: State v. Kuhse, No. 18-0765 (Iowa Jan. 17, 2020, amended Apr. 8, 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/instruction.md (assignment 2 prompt); location: Assignment 2 prompt (email from supervisor).

Authority type: case; as written: State v. Kuhse, No. 18-0765, slip op. (Iowa Apr. 8, 2020) (Kuhse.pdf); pincite: .

Cited for: New authority to analyze (first mention)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Downloaded the official Iowa Supreme Court PDF and compared it with the supplied Kuhse.pdf: identical apart from the source header. The opinion was filed January 17, 2020 and amended April 8, 2020; the prompt's 'Apr. 8, 2020' date refers to the amended opinion actually supplied. (CourtListener's copy is the January 17 version, which lacks the 'Amended April 8, 2020' line and spells 'Lindsay' for 'Lindsey'.)

Excerpt read: IN THE SUPREME COURT OF IOWA No. 18-0765 Filed January 17, 2020 Amended April 8, 2020 STATE OF IOWA, Appellee, vs. KEN LORENZE KUHSE, Appellant.

- https://www.iowacourts.gov/courtcases/6442/embed/SupremeCourtOpinion
- https://www.courtlistener.com/opinion/4707435/state-of-iowa-v-ken-lorenze-kuhse/

### Second check: not required


## A2-PROMPT-002: State v. Kuhse, No. 18-0765 (Iowa Jan. 17, 2020, amended Apr. 8, 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/instruction.md (assignment 2 prompt); location: Assignment 2 prompt (email from supervisor).

Authority type: case; as written: State v. Kuhse, No. 18-0765, slip op. (Iowa Apr. 8, 2020) (Kuhse.pdf); pincite: .

Cited for: Uploaded for use (second mention)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Downloaded the official Iowa Supreme Court PDF and compared it with the supplied Kuhse.pdf: identical apart from the source header. The opinion was filed January 17, 2020 and amended April 8, 2020; the prompt's 'Apr. 8, 2020' date refers to the amended opinion actually supplied. (CourtListener's copy is the January 17 version, which lacks the 'Amended April 8, 2020' line and spells 'Lindsay' for 'Lindsey'.)

Excerpt read: IN THE SUPREME COURT OF IOWA No. 18-0765 Filed January 17, 2020 Amended April 8, 2020 STATE OF IOWA, Appellee, vs. KEN LORENZE KUHSE, Appellant.

- https://www.iowacourts.gov/courtcases/6442/embed/SupremeCourtOpinion
- https://www.courtlistener.com/opinion/4707435/state-of-iowa-v-ken-lorenze-kuhse/

### Second check: not required


## A2-RUBRIC-001: State v. Kuhse, No. 18-0765, slip op. at 9 (Iowa Apr. 8, 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/tests/fixtures/rubric.json (assignment 2 rubric); location: Assignment 2 rubric, criterion_1 (+5), source field.

Authority type: case; as written: State v. Kuhse, No. 18-0765, slip op. at 9 (Iowa Apr. 8, 2020); pincite: 9.

Cited for: Patton bears initial burden of producing evidence for justification instruction

Quotes: ['The defendant bears the initial burden of producing sufficient evidence to support the instruction.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official amended opinion (identical to the supplied file): both quoted sentences appear verbatim at page 9. Kuhse attributes the initial-burden sentence to State v. Delay, 320 N.W.2d at 834 (verified: 'There is no burden on the State to negate an affirmative defense unless the defendant meets his initial burden by producing sufficient evidence'); the burden-shift sentence carries no citation. Kuhse is an Iowa state-law case; whether its standard governs a federal trial instruction is outside this citation check.

Excerpt read: The defendant bears the initial burden of producing sufficient evidence to support the instruction. Id. at 834. Once that threshold is met, the burden shifts to the State to prove lack of justification beyond a reasonable doubt.

- https://www.iowacourts.gov/courtcases/6442/embed/SupremeCourtOpinion
- https://www.courtlistener.com/opinion/1752241/state-v-delay/

### Second check: not required


## A2-RUBRIC-002: State v. Kuhse, No. 18-0765, slip op. at 9 (Iowa Apr. 8, 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/tests/fixtures/rubric.json (assignment 2 rubric); location: Assignment 2 rubric, criterion_2 (+5), source field.

Authority type: case; as written: State v. Kuhse, No. 18-0765, slip op. at 9 (Iowa Apr. 8, 2020); pincite: 9.

Cited for: Burden shifts to the State once threshold met

Quotes: ['Once that threshold is met, the burden shifts to the State to prove lack of justification beyond a reasonable doubt.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official amended opinion (identical to the supplied file): both quoted sentences appear verbatim at page 9. Kuhse attributes the initial-burden sentence to State v. Delay, 320 N.W.2d at 834 (verified: 'There is no burden on the State to negate an affirmative defense unless the defendant meets his initial burden by producing sufficient evidence'); the burden-shift sentence carries no citation. Kuhse is an Iowa state-law case; whether its standard governs a federal trial instruction is outside this citation check.

Excerpt read: The defendant bears the initial burden of producing sufficient evidence to support the instruction. Id. at 834. Once that threshold is met, the burden shifts to the State to prove lack of justification beyond a reasonable doubt.

- https://www.iowacourts.gov/courtcases/6442/embed/SupremeCourtOpinion
- https://www.courtlistener.com/opinion/1752241/state-v-delay/

### Second check: not required


## A2-RUBRIC-003: State v. Kuhse, No. 18-0765, slip op. at 9 (Iowa Apr. 8, 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/tests/fixtures/rubric.json (assignment 2 rubric); location: Assignment 2 rubric, criterion_10 (+10), source field.

Authority type: case; as written: State v. Kuhse, No. 18-0765, slip op. at 9 (Iowa Apr. 8, 2020); pincite: 9.

Cited for: Patton failed to produce substantial evidence of self-defense

Quotes: ['The defendant bears the initial burden of producing sufficient evidence to support the instruction.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official amended opinion (identical to the supplied file): both quoted sentences appear verbatim at page 9. Kuhse attributes the initial-burden sentence to State v. Delay, 320 N.W.2d at 834 (verified: 'There is no burden on the State to negate an affirmative defense unless the defendant meets his initial burden by producing sufficient evidence'); the burden-shift sentence carries no citation. Kuhse is an Iowa state-law case; whether its standard governs a federal trial instruction is outside this citation check.

Excerpt read: The defendant bears the initial burden of producing sufficient evidence to support the instruction. Id. at 834. Once that threshold is met, the burden shifts to the State to prove lack of justification beyond a reasonable doubt.

- https://www.iowacourts.gov/courtcases/6442/embed/SupremeCourtOpinion
- https://www.courtlistener.com/opinion/1752241/state-v-delay/

### Second check: not required


## POE-001: 18 U.S.C. § 922(g)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 1 (slip op. at 1).

Authority type: statute; as written: 18 U.S.C. § 922(g)(1); pincite: .

Cited for: Offense of conviction (felon in possession)

Quotes: []

Context: Opening paragraph stating Poe's conviction.

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 922(g)(1) prohibits possession by a person convicted of a crime punishable by more than one year, consistent with Poe's felon-in-possession conviction.

Excerpt read: (g) It shall be unlawful for any person-- (1) who has been convicted in any court of, a crime punishable by imprisonment for a term exceeding one year;

- https://www.law.cornell.edu/uscode/text/18/922

### Second check: not required


## POE-002: 18 U.S.C. § 924(e)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 1 (slip op. at 1).

Authority type: statute; as written: 18 U.S.C. § 924(e); pincite: .

Cited for: Armed career criminal classification

Quotes: []

Context: Opening paragraph on sentence.

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 924(e)(1) is the armed career criminal enhancement for § 922(g) violators with three prior violent felony or serious drug convictions.

Excerpt read: In the case of a person who violates section 922(g) of this title and has three previous convictions by any court referred to in section 922(g)(1) of this title for a violent felony or a serious drug offense, or both ...

- https://www.law.cornell.edu/uscode/text/18/924

### Second check: not required


## POE-003: 18 U.S.C. § 922(g)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 2 (slip op. at 2).

Authority type: statute; as written: 18 U.S.C. § 922(g)(1); pincite: .

Cited for: Charge against Poe

Quotes: []

Context: Part I facts.

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 922(g)(1) prohibits possession by a person convicted of a crime punishable by more than one year, consistent with Poe's felon-in-possession conviction.

Excerpt read: (g) It shall be unlawful for any person-- (1) who has been convicted in any court of, a crime punishable by imprisonment for a term exceeding one year;

- https://www.law.cornell.edu/uscode/text/18/922

### Second check: not required


## POE-004: United States v. Johnson, 278 F.3d 749 (8th Cir. 2002)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 3 (slip op. at 3).

Authority type: case; as written: United States v. Johnson, 278 F.3d 749, 751-52 (8th Cir. 2002); pincite: 751-52.

Cited for: District court's broad discretion; entitlement to instruction that correctly states law and is supported by evidence

Quotes: ['it correctly states the law and is supported by the evidence']

Context: Part II standard of review.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text. At 751-52 the court states the district court has broad discretion in formulating instructions; at 752 a defendant is entitled to a requested theory-of-defense instruction if it correctly states the law and is supported by the evidence. Quoted phrase appears verbatim.

Excerpt read: The district court has broad discretion in formulating the jury instructions. ... A defendant is entitled to a timely requested instruction on his theory of defense as long as it correctly states the law and is supported by the evidence.

- https://www.courtlistener.com/opinion/776342/united-states-v-joseph-j-johnson/

### Second check: not required


## POE-005: United States v. Hudson, 414 F.3d 931 (8th Cir. 2005)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 3 (slip op. at 3).

Authority type: case; as written: United States v. Hudson, 414 F.3d 931, 933 (8th Cir. 2005); pincite: 933.

Cited for: Sufficiency of evidence to submit affirmative-defense instruction is a question of law reviewed de novo

Quotes: []

Context: Part II; this is the sentence the assignment 1 rubric quotes.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with star pagination. At 933: de novo review of whether there is sufficient evidence to submit an affirmative defense, and the 'underlying evidentiary foundation' standard quoting Kabat. At 934: reasonable legal alternatives defeat the third element.

Excerpt read: We review de novo a district court's decision whether there is sufficient evidence to submit an affirmative defense to a jury. ... a defendant is entitled to a jury instruction concerning an available justification defense if she shows "an 'underlying evidentiary foundation' as to each element of the defense" ... [*934] One reasonable alternative for Hudson was to report her alleged fear ...

- https://www.courtlistener.com/opinion/790993/united-states-v-edith-madora-hudson-also-known-as-edith-madora-spicer/

### Second check: not required


## POE-006: 18 U.S.C. § 922(g)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 3 (slip op. at 3).

Authority type: statute; as written: § 922(g); pincite: .

Cited for: Statute to which justification defense has not been recognized

Quotes: []

Context: Luker sentence.

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 922(g)(1) prohibits possession by a person convicted of a crime punishable by more than one year, consistent with Poe's felon-in-possession conviction.

Excerpt read: (g) It shall be unlawful for any person-- (1) who has been convicted in any court of, a crime punishable by imprisonment for a term exceeding one year;

- https://www.law.cornell.edu/uscode/text/18/922

### Second check: not required


## POE-007: United States v. Luker, 395 F.3d 830 (8th Cir. 2005)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 3 (slip op. at 3).

Authority type: case; as written: United States v. Luker, 395 F.3d 830, 832 (8th Cir. 2005); pincite: 832.

Cited for: Eighth Circuit has never recognized justification as a defense to § 922(g)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text. After the *832 page marker the court notes the Eighth Circuit has never validated justification as a defense to a § 922(g) violation.

Excerpt read: We first note that the Eighth Circuit has never validated justification as a defense to a section 922(g) violation.

- https://www.courtlistener.com/opinion/788993/united-states-v-tony-john-luker/

### Second check: not required


## POE-008: United States v. Stover, 822 F.2d 48 (8th Cir. 1987)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: United States v. Stover, 822 F.2d 48, 50 n.3 (8th Cir. 1987); pincite: 50 n.3.

Cited for: Eighth Circuit would follow the Fifth Circuit's articulation of the justification elements

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read full CourtListener text; footnote 3 (at 50 n.3) endorses the Fifth Circuit's Gant formulation as 'an accurate statement of the justification defense', supporting Poe's characterization.

Excerpt read: An accurate statement of the justification defense is found in United States v. Gant, 691 F.2d 1159 (5th Cir.1982) ... (4) "that a direct causal relationship may be reasonably anticipated between the [criminal] action taken and the avoidance of the [threatened] harm." ... the defense of justification had no applicability to Stover's possession of the gun after John left the scene

- https://www.courtlistener.com/opinion/490237/united-states-v-ronald-stover/

### Second check: not required


## POE-009: United States v. Stover, 822 F.2d 48 (8th Cir. 1987)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: Id. (alterations in original) [Stover, 822 F.2d at 50 n.3]; pincite: 50 n.3.

Cited for: Four elements of the justification defense

Quotes: ['(1) that defendant was under an unlawful and "present, imminent, and impending [threat] of such a nature as to induce a well-grounded apprehension of death or serious bodily injury,"', '(4) "that a direct causal relationship may be reasonably anticipated between the [criminal] action and the avoidance of the [threatened] harm."']

Context: Id. resolves to Stover.

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read full CourtListener text. Footnote 3 (at 50 n.3) adopts the Fifth Circuit's Gant formulation of the justification elements, and at 50 the court holds justification inapplicable once the assailant left and Stover (who waited five to ten minutes) was no longer in imminent danger. Poe's quotation of element (4), marked 'alterations in original', omits the word 'taken' that appears after '[criminal] action' in Stover's footnote; otherwise the quotation matches.

Excerpt read: An accurate statement of the justification defense is found in United States v. Gant, 691 F.2d 1159 (5th Cir.1982) ... (4) "that a direct causal relationship may be reasonably anticipated between the [criminal] action taken and the avoidance of the [threatened] harm." ... the defense of justification had no applicability to Stover's possession of the gun after John left the scene

- https://www.courtlistener.com/opinion/490237/united-states-v-ronald-stover/

### Second check: not required


## POE-010: United States v. Hudson, 414 F.3d 931 (8th Cir. 2005)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: Hudson, 414 F.3d at 933; pincite: 933.

Cited for: Defendant must show an underlying evidentiary foundation as to each element

Quotes: ["an 'underlying evidentiary foundation' as to each element of the defense"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with star pagination. At 933: de novo review of whether there is sufficient evidence to submit an affirmative defense, and the 'underlying evidentiary foundation' standard quoting Kabat. At 934: reasonable legal alternatives defeat the third element.

Excerpt read: We review de novo a district court's decision whether there is sufficient evidence to submit an affirmative defense to a jury. ... a defendant is entitled to a jury instruction concerning an available justification defense if she shows "an 'underlying evidentiary foundation' as to each element of the defense" ... [*934] One reasonable alternative for Hudson was to report her alleged fear ...

- https://www.courtlistener.com/opinion/790993/united-states-v-edith-madora-hudson-also-known-as-edith-madora-spicer/

### Second check: not required


## POE-011: United States v. Kabat, 797 F.2d 580 (8th Cir. 1986)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: United States v. Kabat, 797 F.2d 580, 590-91 (8th Cir 1986); pincite: 590-91.

Cited for: Source of 'underlying evidentiary foundation' standard (quoted via Hudson)

Quotes: ['underlying evidentiary foundation']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text. The 'underlying evidentiary foundation' language straddles the *591 page marker, matching the 590-91 pin.

Excerpt read: It is sufficient that the defendant have shown an [*591] "underlying evidentiary foundation" as to each element of the defense, "regardless of how weak, inconsistent or dubious" the evidence on a given point may seem.

- https://www.courtlistener.com/opinion/8952692/united-states-v-kabat/

### Second check: not required


## POE-012: 18 U.S.C. § 922(g)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: § 922(g); pincite: .

Cited for: Court need not decide whether justification is available to a § 922(g) violation

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 922(g)(1) prohibits possession by a person convicted of a crime punishable by more than one year, consistent with Poe's felon-in-possession conviction.

Excerpt read: (g) It shall be unlawful for any person-- (1) who has been convicted in any court of, a crime punishable by imprisonment for a term exceeding one year;

- https://www.law.cornell.edu/uscode/text/18/922

### Second check: not required


## POE-013: United States v. Stover, 822 F.2d 48 (8th Cir. 1987)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: In Stover ... 822 F.2d at 50; pincite: 50.

Cited for: No imminent danger where defendant retained assailant's gun about 10 minutes after assailant fled

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read full CourtListener text; at 50 Stover holds justification inapplicable to possession after the assailant left, Stover having waited five to ten minutes. Supports Poe's description.

Excerpt read: An accurate statement of the justification defense is found in United States v. Gant, 691 F.2d 1159 (5th Cir.1982) ... (4) "that a direct causal relationship may be reasonably anticipated between the [criminal] action taken and the avoidance of the [threatened] harm." ... the defense of justification had no applicability to Stover's possession of the gun after John left the scene

- https://www.courtlistener.com/opinion/490237/united-states-v-ronald-stover/

### Second check: not required


## POE-014: United States v. Hudson, 414 F.3d 931 (8th Cir. 2005)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: See Hudson, 414 F.3d at 934; pincite: 934.

Cited for: Reasonable alternatives to possessing the gun defeat the defense

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with star pagination. At 933: de novo review of whether there is sufficient evidence to submit an affirmative defense, and the 'underlying evidentiary foundation' standard quoting Kabat. At 934: reasonable legal alternatives defeat the third element.

Excerpt read: We review de novo a district court's decision whether there is sufficient evidence to submit an affirmative defense to a jury. ... a defendant is entitled to a jury instruction concerning an available justification defense if she shows "an 'underlying evidentiary foundation' as to each element of the defense" ... [*934] One reasonable alternative for Hudson was to report her alleged fear ...

- https://www.courtlistener.com/opinion/790993/united-states-v-edith-madora-hudson-also-known-as-edith-madora-spicer/

### Second check: not required


## POE-015: United States v. Singleton, 902 F.2d 471 (6th Cir. 1990)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Poe.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: United States v. Singleton, 902 F.2d 471, 473 (6th Cir. 1990); pincite: 473.

Cited for: Defendant must get rid of the firearm as soon as a safe opportunity arises

Quotes: ['Corollary to the requirement that the defendant have no alternative to possession of the firearm is the requirement that the defendant get rid of the firearm as soon as a safe opportunity arises.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text. The quoted sentence appears verbatim after the *473 page marker.

Excerpt read: Corollary to the requirement that the defendant have no alternative to possession of the firearm is the requirement that the defendant get rid of the firearm as soon as a safe opportunity arises.

- https://www.courtlistener.com/opinion/540842/united-states-v-leonard-d-singleton/

### Second check: not required


## WHITEHORSE-001: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 1 (slip op. at 1).

Authority type: statute; as written: 18 U.S.C. § 1512(c)(1); pincite: .

Cited for: Offense of conviction (tampering with evidence)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-002: United States v. Williams, 605 F.3d 556 (8th Cir. 2010)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 2 (slip op. at 2).

Authority type: case; as written: United States v. Williams, 605 F.3d 556, 567 (8th Cir. 2010); pincite: 567.

Cited for: Jury instructions reviewed for abuse of discretion

Quotes: []

Context: Part II; the sentence the assignment 1 rubric quotes as 'review[s] jury instructions for an abuse of discretion'.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; between the *567 and *568 page markers Williams (quoting Katz) states the abuse-of-discretion standard, the 'taken as a whole, fairly and adequately submitted' test, and the 'broad discretion ... technically perfect or even a model of clarity' sentence that White Horse quotes.

Excerpt read: "We review the district court's jury instructions for abuse of discretion, and this court will affirm if the instructions, taken as a whole, fairly and adequately submitted the issues to the jury." ... "A district court has broad discretion in instructing the jury, and jury instructions do not need to be technically perfect or even a model of clarity."

- https://www.courtlistener.com/opinion/146806/united-states-v-bobby-williams-jr/

### Second check: not required


## WHITEHORSE-003: United States v. Williams, 605 F.3d 556 (8th Cir. 2010)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: case; as written: Id. [Williams, 605 F.3d at 567]; pincite: 567.

Cited for: Broad discretion; instructions need not be technically perfect

Quotes: ['A district court has broad discretion in instructing the jury, and jury instructions do not need to be technically perfect or even a model of clarity.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; between the *567 and *568 page markers Williams (quoting Katz) states the abuse-of-discretion standard, the 'taken as a whole, fairly and adequately submitted' test, and the 'broad discretion ... technically perfect or even a model of clarity' sentence that White Horse quotes.

Excerpt read: "We review the district court's jury instructions for abuse of discretion, and this court will affirm if the instructions, taken as a whole, fairly and adequately submitted the issues to the jury." ... "A district court has broad discretion in instructing the jury, and jury instructions do not need to be technically perfect or even a model of clarity."

- https://www.courtlistener.com/opinion/146806/united-states-v-bobby-williams-jr/

### Second check: not required


## WHITEHORSE-004: United States v. Williams, 605 F.3d 556 (8th Cir. 2010)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: case; as written: Id. [Williams, 605 F.3d at 567]; pincite: 567.

Cited for: Affirm if instructions taken as a whole fairly and adequately submitted the issues

Quotes: ['affirm if the instructions, taken as a whole, fairly and adequately submitted the issues to the jury.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; between the *567 and *568 page markers Williams (quoting Katz) states the abuse-of-discretion standard, the 'taken as a whole, fairly and adequately submitted' test, and the 'broad discretion ... technically perfect or even a model of clarity' sentence that White Horse quotes.

Excerpt read: "We review the district court's jury instructions for abuse of discretion, and this court will affirm if the instructions, taken as a whole, fairly and adequately submitted the issues to the jury." ... "A district court has broad discretion in instructing the jury, and jury instructions do not need to be technically perfect or even a model of clarity."

- https://www.courtlistener.com/opinion/146806/united-states-v-bobby-williams-jr/

### Second check: not required


## WHITEHORSE-005: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: statute; as written: § 1512(c)(1); pincite: .

Cited for: Text of the tampering statute

Quotes: ["corruptly . . . conceal[ing] a record, document, or other object, or attempt[ing] to do so, with the intent to impair the object's integrity or availability for use in an official proceeding."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-006: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: statute; as written: § 1512(c)(1); pincite: .

Cited for: Applying knowledge principle to the statute

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-007: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: statute; as written: § 1512(c)(1); pincite: .

Cited for: Conviction requires proof of nexus to official proceeding

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-008: United States v. Aguilar, 515 U.S. 593 (1995)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: case; as written: United States v. Aguilar, 515 U.S. 593, 595, 598 (1995); pincite: 595, 598.

Cited for: Aguilar addressed § 1503's omnibus clause

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority opinion with page markers. § 1503 conviction and statutory text discussed at 595-98; at 599 the Court holds that a defendant who lacks knowledge his actions are likely to affect the judicial proceeding lacks the requisite intent; at 602 the 'culpability is a good deal less clear' passage. Quotations attributed to Aguilar in White Horse appear verbatim at the cited pages.

Excerpt read: But as in Pettibone, if the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct. [*600] ... [*602] The intent to obstruct justice is indeed present, but the man's culpability is a good deal less clear from the statute than we usually require in order to impose criminal liability.

- https://www.courtlistener.com/opinion/117962/united-states-v-aguilar/

### Second check: not required


## WHITEHORSE-009: 18 U.S.C. § 1503

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: statute; as written: 18 U.S.C. § 1503; pincite: .

Cited for: Prohibits corruptly endeavoring to obstruct the due administration of justice

Quotes: ['corruptly . . . endeavor[ing] to . . . obstruct . . . the due administration of justice.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; the omnibus clause prohibits whoever 'corruptly ... endeavors to influence, obstruct, or impede, the due administration of justice', matching White Horse's bracketed quotation.

Excerpt read: or by any threatening letter or communication, influences, obstructs, or impedes, or endeavors to influence, obstruct, or impede, the due administration of justice, shall be punished

- https://www.law.cornell.edu/uscode/text/18/1503

### Second check: not required


## WHITEHORSE-010: United States v. Aguilar, 515 U.S. 593 (1995)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: case; as written: See id. at 599, 602 [Aguilar]; pincite: 599, 602.

Cited for: Violation requires knowledge that action is likely to obstruct

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority opinion with page markers. § 1503 conviction and statutory text discussed at 595-98; at 599 the Court holds that a defendant who lacks knowledge his actions are likely to affect the judicial proceeding lacks the requisite intent; at 602 the 'culpability is a good deal less clear' passage. Quotations attributed to Aguilar in White Horse appear verbatim at the cited pages.

Excerpt read: But as in Pettibone, if the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct. [*600] ... [*602] The intent to obstruct justice is indeed present, but the man's culpability is a good deal less clear from the statute than we usually require in order to impose criminal liability.

- https://www.courtlistener.com/opinion/117962/united-states-v-aguilar/

### Second check: not required


## WHITEHORSE-011: United States v. Yielding, 657 F.3d 688 (8th Cir. 2011)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: case; as written: United States v. Yielding, 657 F.3d 688, 713 (8th Cir. 2011); pincite: 713.

Cited for: Aguilar interpreted 'corruptly endeavor[ing]' to require knowledge of natural and probable effect

Quotes: ["proof that the accused knew of a 'natural and probable effect' on a federal proceeding"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; after the *713 marker the court explains that Aguilar, construing the ambiguous phrase 'corruptly endeavor', required proof that the accused knew of a 'natural and probable effect' on a federal proceeding. Matches White Horse's parentheticals.

Excerpt read: Exercising restraint based on concerns about fair warning and deference to Congress, the Court required proof that the accused knew of a "natural and probable effect" on a federal proceeding to establish an intent to obstruct. ... The statute includes no ambiguous phrase such as "corruptly endeavor"

- https://www.courtlistener.com/opinion/614777/united-states-v-yielding/

### Second check: not required


## WHITEHORSE-012: United States v. Friske, 640 F.3d 1288 (11th Cir. 2011)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: case; as written: United States v. Friske, 640 F.3d 1288, 1291 (11th Cir. 2011); pincite: 1291.

Cited for: Aguilar's holding is an articulation of the mens rea of 'corruptly'

Quotes: ["is best understood as an articulation of the proof of wrongful intent that will satisfy the mens rea requirement of 'corruptly' obstructing"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted sentence appears at 1291 (between the *1291 and *1292 markers), where Friske itself quotes sister circuits.

Excerpt read: As our sister circuits have explained, "[t]he nexus limitation is best understood as an articulation of the proof of wrongful intent that will satisfy the mens rea requirement of 'corruptly' obstructing."

- https://www.courtlistener.com/opinion/216931/united-states-v-friske/

### Second check: not required


## WHITEHORSE-013: United States v. Erickson, 561 F.3d 1150 (10th Cir. 2009)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: case; as written: United States v. Erickson, 561 F.3d 1150, 1159 (10th Cir. 2009); pincite: 1159.

Cited for: (same)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; after the *1159 marker Erickson quotes Aguilar at 599 and states the nexus limitation is best understood as an articulation of the mens rea of 'corruptly'. Supports the '(same)' parenthetical.

Excerpt read: "The nexus limitation is best understood as an articulation of the proof of wrongful intent that will satisfy the mens rea requirement of 'corrupt[ly]' obstructing ..."

- https://www.courtlistener.com/opinion/171981/united-states-v-erickson/

### Second check: not required


## WHITEHORSE-014: United States v. Quattrone, 441 F.3d 153 (2d Cir. 2006)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 3 (slip op. at 3).

Authority type: case; as written: United States v. Quattrone, 441 F.3d 153, 170 (2d Cir. 2006); pincite: 170.

Cited for: (same)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; between the *170 and *171 markers the court states the nexus limitation is best understood as an articulation of the mens rea requirement of 'corruptly' obstructing. Supports the '(same)' parenthetical.

Excerpt read: The nexus limitation is best understood as an articulation of the proof of wrongful intent that will satisfy the mens rea requirement of "corruptly" obstructing or endeavoring to obstruct.

- https://www.courtlistener.com/opinion/793659/united-states-v-frank-quattrone/

### Second check: not required


## WHITEHORSE-015: 18 U.S.C. § 1503

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF pages 3-4 (slip op. at 3-4).

Authority type: statute; as written: § 1503; pincite: .

Cited for: 'Corruptly' is the only relevant mens rea term in § 1503 other than 'endeavors'

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; the omnibus clause prohibits whoever 'corruptly ... endeavors to influence, obstruct, or impede, the due administration of justice', matching White Horse's bracketed quotation.

Excerpt read: or by any threatening letter or communication, influences, obstructs, or impedes, or endeavors to influence, obstruct, or impede, the due administration of justice, shall be punished

- https://www.law.cornell.edu/uscode/text/18/1503

### Second check: not required


## WHITEHORSE-016: United States v. Russell, 255 U.S. 138 (1921)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: United States v. Russell, 255 U.S. 138, 143 (1921); pincite: 143.

Cited for: Interpreting 'endeavor'

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; at 143 the Court explains that 'endeavor' describes any effort to accomplish the evil purpose and that success is not required, supporting White Horse's point that 'endeavors' imports only an intention requirement.

Excerpt read: The word of the section is "endeavor," and by using it the section got rid of the technicalities which might be urged as besetting the word "attempt," and it describes any effort or essay to accomplish the evil purpose that the section was enacted to prevent.

- https://www.courtlistener.com/opinion/99724/united-states-v-russell/

### Second check: not required


## WHITEHORSE-017: 18 U.S.C. § 1503

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: § 1503; pincite: .

Cited for: 'Corruptly' is the only term in § 1503 modifying 'endeavors to . . . obstruct'

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; the omnibus clause prohibits whoever 'corruptly ... endeavors to influence, obstruct, or impede, the due administration of justice', matching White Horse's bracketed quotation.

Excerpt read: or by any threatening letter or communication, influences, obstructs, or impedes, or endeavors to influence, obstruct, or impede, the due administration of justice, shall be punished

- https://www.law.cornell.edu/uscode/text/18/1503

### Second check: not required


## WHITEHORSE-018: United States v. Aguilar, 515 U.S. 593 (1995)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: See Aguilar, 515 U.S. at 599; pincite: 599.

Cited for: Defendant lacking knowledge lacks requisite intent

Quotes: ['if the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority opinion with page markers. § 1503 conviction and statutory text discussed at 595-98; at 599 the Court holds that a defendant who lacks knowledge his actions are likely to affect the judicial proceeding lacks the requisite intent; at 602 the 'culpability is a good deal less clear' passage. Quotations attributed to Aguilar in White Horse appear verbatim at the cited pages.

Excerpt read: But as in Pettibone, if the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct. [*600] ... [*602] The intent to obstruct justice is indeed present, but the man's culpability is a good deal less clear from the statute than we usually require in order to impose criminal liability.

- https://www.courtlistener.com/opinion/117962/united-states-v-aguilar/

### Second check: not required


## WHITEHORSE-019: United States v. Aguilar, 515 U.S. 593 (1995)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: id. at 602 [Aguilar]; pincite: 602.

Cited for: Culpability less clear without knowledge

Quotes: ['culpability is a good deal less clear', 'intent to obstruct']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority opinion with page markers. § 1503 conviction and statutory text discussed at 595-98; at 599 the Court holds that a defendant who lacks knowledge his actions are likely to affect the judicial proceeding lacks the requisite intent; at 602 the 'culpability is a good deal less clear' passage. Quotations attributed to Aguilar in White Horse appear verbatim at the cited pages.

Excerpt read: But as in Pettibone, if the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct. [*600] ... [*602] The intent to obstruct justice is indeed present, but the man's culpability is a good deal less clear from the statute than we usually require in order to impose criminal liability.

- https://www.courtlistener.com/opinion/117962/united-states-v-aguilar/

### Second check: not required


## WHITEHORSE-020: Arthur Andersen LLP v. United States, 544 U.S. 696 (2005)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: Arthur Anderson LLP v. United States, 544 U.S. 696 (2005); pincite: .

Cited for: Court confirmed this reading of Aguilar

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener text with page markers. § 1512(b) quoted at 702-03; discussion that persuasion is not inherently malign and of 'corruptly' at 703-05; at 707-08 the Court relies on Aguilar, 515 U.S. at 599-600, that a defendant lacking knowledge his actions are likely to affect the proceeding lacks the requisite intent. Propositions supported. Defect: the case name is spelled 'Arthur Anderson' throughout White Horse; the party is Arthur Andersen LLP (spelling error in the court's slip opinion).

Excerpt read: [*708] ... We faced a similar situation in Aguilar, supra. ... We held that § 1503 required something more -- specifically, a "nexus" between the obstructive act and the proceeding. Id., at 599-600. "[I]f the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct."

- https://www.courtlistener.com/opinion/142899/arthur-andersen-llp-v-united-states/

### Second check: not required


## WHITEHORSE-021: 18 U.S.C. § 1512(b)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: 18 U.S.C. § 1512(b); pincite: .

Cited for: Prohibits corruptly persuading another with intent

Quotes: ['corruptly persuad[ing] another person, or attempt[ing] to do so, . . . with intent to']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1512(b) reaches whoever 'corruptly persuades another person, or attempts to do so, ... with intent to' accomplish enumerated objectives, matching White Horse's bracketed quotation.

Excerpt read: (b) Whoever knowingly uses intimidation, threatens, or corruptly persuades another person, or attempts to do so, or engages in misleading conduct toward another person, with intent to--

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-022: Arthur Andersen LLP v. United States, 544 U.S. 696 (2005)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: 544 U.S. at 702-03; pincite: 702-03.

Cited for: Statutory text addressed in Arthur Andersen

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener text with page markers. § 1512(b) quoted at 702-03; discussion that persuasion is not inherently malign and of 'corruptly' at 703-05; at 707-08 the Court relies on Aguilar, 515 U.S. at 599-600, that a defendant lacking knowledge his actions are likely to affect the proceeding lacks the requisite intent. Propositions supported. Defect: the case name is spelled 'Arthur Anderson' throughout White Horse; the party is Arthur Andersen LLP (spelling error in the court's slip opinion).

Excerpt read: [*708] ... We faced a similar situation in Aguilar, supra. ... We held that § 1503 required something more -- specifically, a "nexus" between the obstructive act and the proceeding. Id., at 599-600. "[I]f the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct."

- https://www.courtlistener.com/opinion/142899/arthur-andersen-llp-v-united-states/

### Second check: not required


## WHITEHORSE-023: 18 U.S.C. § 1512(b)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: § 1512(b); pincite: .

Cited for: Enumerated objectives of § 1512(b)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1512(b) reaches whoever 'corruptly persuades another person, or attempts to do so, ... with intent to' accomplish enumerated objectives, matching White Horse's bracketed quotation.

Excerpt read: (b) Whoever knowingly uses intimidation, threatens, or corruptly persuades another person, or attempts to do so, or engages in misleading conduct toward another person, with intent to--

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-024: Arthur Andersen LLP v. United States, 544 U.S. 696 (2005)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: Id. at 703-05; pincite: 703-05.

Cited for: Not every persuasion with intent is 'corrupt'

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener text with page markers. § 1512(b) quoted at 702-03; discussion that persuasion is not inherently malign and of 'corruptly' at 703-05; at 707-08 the Court relies on Aguilar, 515 U.S. at 599-600, that a defendant lacking knowledge his actions are likely to affect the proceeding lacks the requisite intent. Propositions supported. Defect: the case name is spelled 'Arthur Anderson' throughout White Horse; the party is Arthur Andersen LLP (spelling error in the court's slip opinion).

Excerpt read: [*708] ... We faced a similar situation in Aguilar, supra. ... We held that § 1503 required something more -- specifically, a "nexus" between the obstructive act and the proceeding. Id., at 599-600. "[I]f the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct."

- https://www.courtlistener.com/opinion/142899/arthur-andersen-llp-v-united-states/

### Second check: not required


## WHITEHORSE-025: Arthur Andersen LLP v. United States, 544 U.S. 696 (2005)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: See id. at 708; pincite: 708.

Cited for: Persuader must know he is likely to accomplish his intention

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener text with page markers. § 1512(b) quoted at 702-03; discussion that persuasion is not inherently malign and of 'corruptly' at 703-05; at 707-08 the Court relies on Aguilar, 515 U.S. at 599-600, that a defendant lacking knowledge his actions are likely to affect the proceeding lacks the requisite intent. Propositions supported. Defect: the case name is spelled 'Arthur Anderson' throughout White Horse; the party is Arthur Andersen LLP (spelling error in the court's slip opinion).

Excerpt read: [*708] ... We faced a similar situation in Aguilar, supra. ... We held that § 1503 required something more -- specifically, a "nexus" between the obstructive act and the proceeding. Id., at 599-600. "[I]f the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct."

- https://www.courtlistener.com/opinion/142899/arthur-andersen-llp-v-united-states/

### Second check: not required


## WHITEHORSE-026: United States v. Aguilar, 515 U.S. 593 (1995)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: case; as written: citing Aguilar, 515 U.S. at 599-600; pincite: 599-600.

Cited for: Source relied on by Arthur Andersen

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority opinion with page markers. § 1503 conviction and statutory text discussed at 595-98; at 599 the Court holds that a defendant who lacks knowledge his actions are likely to affect the judicial proceeding lacks the requisite intent; at 602 the 'culpability is a good deal less clear' passage. Quotations attributed to Aguilar in White Horse appear verbatim at the cited pages.

Excerpt read: But as in Pettibone, if the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct. [*600] ... [*602] The intent to obstruct justice is indeed present, but the man's culpability is a good deal less clear from the statute than we usually require in order to impose criminal liability.

- https://www.courtlistener.com/opinion/117962/united-states-v-aguilar/

### Second check: not required


## WHITEHORSE-027: 18 U.S.C. § 1503

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: §§ 1503; pincite: .

Cited for: Uses 'corruptly' with an intention requirement

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; the omnibus clause prohibits whoever 'corruptly ... endeavors to influence, obstruct, or impede, the due administration of justice', matching White Horse's bracketed quotation.

Excerpt read: or by any threatening letter or communication, influences, obstructs, or impedes, or endeavors to influence, obstruct, or impede, the due administration of justice, shall be punished

- https://www.law.cornell.edu/uscode/text/18/1503

### Second check: not required


## WHITEHORSE-028: 18 U.S.C. § 1512(b)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: [§§ 1503 and] 1512(b); pincite: .

Cited for: Uses 'corruptly' with an intention requirement

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1512(b) reaches whoever 'corruptly persuades another person, or attempts to do so, ... with intent to' accomplish enumerated objectives, matching White Horse's bracketed quotation.

Excerpt read: (b) Whoever knowingly uses intimidation, threatens, or corruptly persuades another person, or attempts to do so, or engages in misleading conduct toward another person, with intent to--

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-029: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: § 1512(c)(1); pincite: .

Cited for: Uses 'corruptly' with an intention requirement

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-030: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: § 1512(c)(1); pincite: .

Cited for: Language very similar to § 1512(b)(2)(B)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-031: 18 U.S.C. § 1512(b)(2)(B)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: § 1512(b)(2)(B); pincite: .

Cited for: Comparator provision

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; (b)(2)(B) covers inducing any person to 'alter, destroy, mutilate, or conceal an object with intent to impair the object's integrity or availability for use in an official proceeding', matching White Horse's comparison quotation.

Excerpt read: (2) cause or induce any person to-- ... (B) alter, destroy, mutilate, or conceal an object with intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-032: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: Compare § 1512(c)(1); pincite: .

Cited for: Quoted text for comparison

Quotes: ["corruptly . . . conceal[ing] a record, document, or other object, or attempt[ing] to do so, with the intent to impair the object's integrity or availability for use in an official proceeding"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-033: 18 U.S.C. § 1512(b)(2)(B)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: with § 1512(b)(2)(B); pincite: .

Cited for: Quoted text for comparison

Quotes: ["corruptly persuad[ing] another person, or attempt[ing] to do so, . . . with intent to . . . induce any person to . . . conceal an object with intent to impair the object's integrity or availability for use in an official proceeding"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; (b)(2)(B) covers inducing any person to 'alter, destroy, mutilate, or conceal an object with intent to impair the object's integrity or availability for use in an official proceeding', matching White Horse's comparison quotation.

Excerpt read: (2) cause or induce any person to-- ... (B) alter, destroy, mutilate, or conceal an object with intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-034: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: § 1512(c)(1)'s mens rea requirement; pincite: .

Cited for: Mens rea requires knowledge of likely success

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-035: United States v. Petruk, 781 F.3d 438 (8th Cir. 2015)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: United States v. Petruk, 781 F.3d 438, 445 (8th Cir. 2015); pincite: 445.

Cited for: Extending Aguilar and Andersen to § 1512(c)(2)

Quotes: ['the similarity of statutory language between § 1512(c)(2) and the . . . provision at issue in Aguilar']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; after the *445 marker Petruk applies the nexus requirement to § 1512(c)(2) 'considering the similarity of statutory language between § 1512(c)(2) and the catchall provision at issue in Aguilar'. White Horse's ellipsis replaces 'catchall'.

Excerpt read: Considering the similarity of statutory language between § 1512(c)(2) and the catchall provision at issue in Aguilar, ...

- https://www.courtlistener.com/opinion/2788483/united-states-v-elfred-william-petruk/

### Second check: not required


## WHITEHORSE-036: 18 U.S.C. § 1512(c)(2)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: § 1512(c)(2); pincite: .

Cited for: Provision to which Petruk extended the nexus requirement (in Petruk parenthetical)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; (c)(2) is the residual 'otherwise obstructs, influences, or impedes any official proceeding' clause, consistent with White Horse's reference to Petruk.

Excerpt read: (2) otherwise obstructs, influences, or impedes any official proceeding, or attempts to do so

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-037: United States v. Yielding, 657 F.3d 688 (8th Cir. 2011)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: Yielding, 657 F.3d at 713; pincite: 713.

Cited for: Linking knowledge requirement to 'corruptly'

Quotes: ["that the accused knew of a 'natural and probable effect' on a federal proceeding"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; after the *713 marker the court explains that Aguilar, construing the ambiguous phrase 'corruptly endeavor', required proof that the accused knew of a 'natural and probable effect' on a federal proceeding. Matches White Horse's parentheticals.

Excerpt read: Exercising restraint based on concerns about fair warning and deference to Congress, the Court required proof that the accused knew of a "natural and probable effect" on a federal proceeding to establish an intent to obstruct. ... The statute includes no ambiguous phrase such as "corruptly endeavor"

- https://www.courtlistener.com/opinion/614777/united-states-v-yielding/

### Second check: not required


## WHITEHORSE-038: United States v. Williams, 605 F.3d 556 (8th Cir. 2010)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: See Williams, 605 F.3d at 567; pincite: 567.

Cited for: Instruction 'fairly and adequately' conveyed requirement

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; between the *567 and *568 page markers Williams (quoting Katz) states the abuse-of-discretion standard, the 'taken as a whole, fairly and adequately submitted' test, and the 'broad discretion ... technically perfect or even a model of clarity' sentence that White Horse quotes.

Excerpt read: "We review the district court's jury instructions for abuse of discretion, and this court will affirm if the instructions, taken as a whole, fairly and adequately submitted the issues to the jury." ... "A district court has broad discretion in instructing the jury, and jury instructions do not need to be technically perfect or even a model of clarity."

- https://www.courtlistener.com/opinion/146806/united-states-v-bobby-williams-jr/

### Second check: not required


## WHITEHORSE-039: United States v. Williams, 605 F.3d 556 (8th Cir. 2010)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: See id. [Williams]; pincite: 567.

Cited for: Instruction need not be technically perfect

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; between the *567 and *568 page markers Williams (quoting Katz) states the abuse-of-discretion standard, the 'taken as a whole, fairly and adequately submitted' test, and the 'broad discretion ... technically perfect or even a model of clarity' sentence that White Horse quotes.

Excerpt read: "We review the district court's jury instructions for abuse of discretion, and this court will affirm if the instructions, taken as a whole, fairly and adequately submitted the issues to the jury." ... "A district court has broad discretion in instructing the jury, and jury instructions do not need to be technically perfect or even a model of clarity."

- https://www.courtlistener.com/opinion/146806/united-states-v-bobby-williams-jr/

### Second check: not required


## WHITEHORSE-040: Arthur Andersen LLP v. United States, 544 U.S. 696 (2005)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: See Arthur Anderson, 544 U.S. at 707-08; pincite: 707-08.

Cited for: Knowledge requirement follows from 'corrupt' intention

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener text with page markers. § 1512(b) quoted at 702-03; discussion that persuasion is not inherently malign and of 'corruptly' at 703-05; at 707-08 the Court relies on Aguilar, 515 U.S. at 599-600, that a defendant lacking knowledge his actions are likely to affect the proceeding lacks the requisite intent. Propositions supported. Defect: the case name is spelled 'Arthur Anderson' throughout White Horse; the party is Arthur Andersen LLP (spelling error in the court's slip opinion).

Excerpt read: [*708] ... We faced a similar situation in Aguilar, supra. ... We held that § 1503 required something more -- specifically, a "nexus" between the obstructive act and the proceeding. Id., at 599-600. "[I]f the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct."

- https://www.courtlistener.com/opinion/142899/arthur-andersen-llp-v-united-states/

### Second check: not required


## WHITEHORSE-041: United States v. Aguilar, 515 U.S. 593 (1995)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: Aguilar, 515 U.S. at 598-602; pincite: 598-602.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority opinion with page markers. § 1503 conviction and statutory text discussed at 595-98; at 599 the Court holds that a defendant who lacks knowledge his actions are likely to affect the judicial proceeding lacks the requisite intent; at 602 the 'culpability is a good deal less clear' passage. Quotations attributed to Aguilar in White Horse appear verbatim at the cited pages.

Excerpt read: But as in Pettibone, if the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct. [*600] ... [*602] The intent to obstruct justice is indeed present, but the man's culpability is a good deal less clear from the statute than we usually require in order to impose criminal liability.

- https://www.courtlistener.com/opinion/117962/united-states-v-aguilar/

### Second check: not required


## WHITEHORSE-042: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: § 1512(c)(1); pincite: .

Cited for: Only intent the defendant knew he was likely to accomplish suffices

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-043: United States v. Franklin, 960 F.3d 1070 (8th Cir. 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: United States v. Franklin, 960 F.3d 1070, 1072-73 (8th Cir. 2020); pincite: 1072-73.

Cited for: Instruction fairly and adequately submitted issue where it conveyed what government must prove

Quotes: ['the government must prove . . . in order to convict']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text (short opinion, 960 F.3d 1070-73). The court held the instructions as a whole conveyed that the government must prove more than proximity to the gun and drugs in order to convict, so no abuse of discretion; White Horse's ellipsis quotation matches.

Excerpt read: the instructions as a whole already conveyed that the government must prove more than proximity to the gun and drugs in order to convict. The district court did not abuse its discretion.

- https://www.courtlistener.com/opinion/4758166/united-states-v-warren-franklin-jr/

### Second check: not required


## WHITEHORSE-044: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: § 1512(c)(1); pincite: .

Cited for: Nexus as independent element argument

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-045: Neder v. United States, 527 U.S. 1 (1999)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: Neder v. United States, 527 U.S. 1, 8 (1999); pincite: 8.

Cited for: Instruction omitting an element is erroneous

Quotes: ['a jury instruction that omits an element of the offense']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority opinion; the Court describes the error as 'a jury instruction that omits an element of the offense' and later notes the instruction's erroneousness is uncontested 'see supra, at 8', confirming the pin.

Excerpt read: The issue here, however, is not whether a jury instruction that omits an element of the offense was error (a point that is uncontested, see supra, at 8), but whether the error is subject to harmless-error analysis.

- https://www.courtlistener.com/opinion/118298/neder-v-united-states/

### Second check: not required


## WHITEHORSE-046: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 6 (slip op. at 6).

Authority type: statute; as written: § 1512(c)(1); pincite: .

Cited for: Defendant cannot violate statute unless action likely to affect proceeding

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-047: United States v. Aguilar, 515 U.S. 593 (1995)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 6 (slip op. at 6).

Authority type: case; as written: Under Aguilar; pincite: .

Cited for: Corrupt intention entails knowledge of likely effect

Quotes: []

Context: Bare case-name reference resolving to Aguilar.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority opinion with page markers. § 1503 conviction and statutory text discussed at 595-98; at 599 the Court holds that a defendant who lacks knowledge his actions are likely to affect the judicial proceeding lacks the requisite intent; at 602 the 'culpability is a good deal less clear' passage. Quotations attributed to Aguilar in White Horse appear verbatim at the cited pages.

Excerpt read: But as in Pettibone, if the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct. [*600] ... [*602] The intent to obstruct justice is indeed present, but the man's culpability is a good deal less clear from the statute than we usually require in order to impose criminal liability.

- https://www.courtlistener.com/opinion/117962/united-states-v-aguilar/

### Second check: not required


## WHITEHORSE-048: Arthur Andersen LLP v. United States, 544 U.S. 696 (2005)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 6 (slip op. at 6).

Authority type: case; as written: and Arthur Anderson; pincite: .

Cited for: Same

Quotes: []

Context: Bare case-name reference resolving to Arthur Andersen.

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener text with page markers. § 1512(b) quoted at 702-03; discussion that persuasion is not inherently malign and of 'corruptly' at 703-05; at 707-08 the Court relies on Aguilar, 515 U.S. at 599-600, that a defendant lacking knowledge his actions are likely to affect the proceeding lacks the requisite intent. Propositions supported. Defect: the case name is spelled 'Arthur Anderson' throughout White Horse; the party is Arthur Andersen LLP (spelling error in the court's slip opinion).

Excerpt read: [*708] ... We faced a similar situation in Aguilar, supra. ... We held that § 1503 required something more -- specifically, a "nexus" between the obstructive act and the proceeding. Id., at 599-600. "[I]f the defendant lacks knowledge that his actions are likely to affect the judicial proceeding, he lacks the requisite intent to obstruct."

- https://www.courtlistener.com/opinion/142899/arthur-andersen-llp-v-united-states/

### Second check: not required


## WHITEHORSE-049: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 6 (slip op. at 6).

Authority type: statute; as written: § 1512(c)(1)'s mens rea requirement; pincite: .

Cited for: Likely-effect requirement implicit in mens rea

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-050: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 6 (slip op. at 6).

Authority type: statute; as written: text of § 1512(c)(1); pincite: .

Cited for: No additional nexus requirement in text

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## WHITEHORSE-051: 18 U.S.C. § 1512(c)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/White Horse.pdf; location: PDF page 6 (slip op. at 6).

Authority type: statute; as written: § 1512(c)(1) violation; pincite: .

Cited for: District court did not omit an element

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII (historical versions at the 2020 conduct and 2022 decision dates were not separately retrieved). White Horse's bracketed quotation matches subsection (c)(1).

Excerpt read: (c) Whoever corruptly-- (1) alters, destroys, mutilates, or conceals a record, document, or other object, or attempts to do so, with the intent to impair the object's integrity or availability for use in an official proceeding;

- https://www.law.cornell.edu/uscode/text/18/1512

### Second check: not required


## KEHOE-001: 18 U.S.C. § 1962(c)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 1 (slip op. at 1).

Authority type: statute; as written: 18 U.S.C. §§ 1962(c) [and (d)]; pincite: .

Cited for: Substantive RICO charge

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; Kehoe's ellipsis quotation matches the current text of § 1962(c); the version in force at the 2002 decision was not separately retrieved.

Excerpt read: (c) It shall be unlawful for any person employed by or associated with any enterprise engaged in, or the activities of which affect, interstate or foreign commerce, to conduct or participate, directly or indirectly, in the conduct of such enterprise's affairs through a pattern of racketeering activity or collection of unlawful debt.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-002: 18 U.S.C. § 1962(d)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 1 (slip op. at 1).

Authority type: statute; as written: [18 U.S.C. §§ 1962(c)] and (d); pincite: .

Cited for: RICO conspiracy charge

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1962(d) makes it unlawful to conspire to violate subsection (a), (b), or (c), matching Kehoe's quotation.

Excerpt read: (d) It shall be unlawful for any person to conspire to violate any of the provisions of subsection (a), (b), or (c) of this section.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-003: 18 U.S.C. § 1959

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 1 (slip op. at 1).

Authority type: statute; as written: 18 U.S.C. § 1959; pincite: .

Cited for: Murder in aid of racketeering charge

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1959(a) punishes violent crimes 'in violation of the laws of any State or the United States' committed for the purpose of gaining or maintaining position in a racketeering enterprise, including attempts (§ 1959(a)(5) covers attempting or conspiring to commit murder). Matches Kehoe's quotation and the prompt's description of attempted murder in aid of racketeering.

Excerpt read: ... for the purpose of gaining entrance to or maintaining or increasing position in an enterprise engaged in racketeering activity, murders, kidnaps, maims, assaults with a dangerous weapon, ... or threatens to commit a crime of violence against any individual in violation of the laws of any State or the United States, or attempts or conspires so to do, shall be punished-- ... (5) for attempting or conspiring to commit murder or kidnapping, by imprisonment for not more than ten years

- https://www.law.cornell.edu/uscode/text/18/1959

### Second check: not required


## KEHOE-004: 18 U.S.C. § 1951(a)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 1 (slip op. at 1).

Authority type: statute; as written: 18 U.S.C. § 1951(a); pincite: .

Cited for: Robbery conspiracy charge

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1951(a) (Hobbs Act) covers robbery affecting commerce and attempts or conspiracies to do so, consistent with the robbery-conspiracy charge Kehoe describes.

Excerpt read: (a) Whoever in any way or degree obstructs, delays, or affects commerce ... by robbery or extortion or attempts or conspires so to do ...

- https://www.law.cornell.edu/uscode/text/18/1951

### Second check: not required


## KEHOE-005: 18 U.S.C. § 3593(a)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 2 (slip op. at 2).

Authority type: statute; as written: 18 U.S.C. § 3593(a); pincite: .

Cited for: Separate penalty proceedings in death-penalty case

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read text at Cornell LII. § 3593(a) is the government's notice of intent to seek death; the separate sentencing hearing Kehoe describes is provided by § 3593(b). Subsection pin is imprecise.

Excerpt read: (a) Notice by the Government.-- If, in a case involving an offense described in section 3591, the attorney for the government believes that the circumstances of the offense are such that a sentence of death is justified ... (b) Hearing Before a Court or Jury.-- If the attorney for the government has filed a notice as required under subsection (a) and the defendant is found guilty ...

- https://www.law.cornell.edu/uscode/text/18/3593

### Second check: not required


## KEHOE-006: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 2 (slip op. at 2).

Authority type: constitution; as written: Fifth [Amendment]; pincite: .

Cited for: Constitutional claims raised on appeal

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## KEHOE-007: U.S. Const. amend. VI

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 2 (slip op. at 2).

Authority type: constitution; as written: Sixth [Amendment]; pincite: .

Cited for: Constitutional claims raised on appeal

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Sixth Amendment text at Cornell LII; it guarantees confrontation and the assistance of counsel.

Excerpt read: to be confronted with the witnesses against him; ... and to have the Assistance of Counsel for his defence.

- https://www.law.cornell.edu/constitution/sixth_amendment

### Second check: not required


## KEHOE-008: U.S. Const. amend. X

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 2 (slip op. at 2).

Authority type: constitution; as written: Tenth Amendments; pincite: .

Cited for: Constitutional claims raised on appeal

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Tenth Amendment text at Cornell LII; Kehoe references it for the state-sovereignty challenge.

Excerpt read: The powers not delegated to the United States by the Constitution, nor prohibited by it to the States, are reserved to the States respectively, or to the people.

- https://www.law.cornell.edu/constitution/tenth_amendment

### Second check: not required


## KEHOE-009: United States v. Gundersen, 195 F.3d 1035 (8th Cir. 1999)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 2 (slip op. at 2).

Authority type: case; as written: United States v. Gundersen, 195 F.3d 1035, 1037 (8th Cir. 1999); pincite: 1037.

Cited for: Facts stated in light most favorable to verdict

Quotes: ["We state the facts in the light most favorable to the jury's verdict."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted sentence opens Part I of the opinion (early in the opinion, consistent with 1037).

Excerpt read: We state the facts in the light most favorable to the jury's verdict.

- https://www.courtlistener.com/opinion/766679/united-states-v-jeffrey-s-gundersen/

### Second check: not required


## KEHOE-010: United States v. Kragness, 830 F.2d 842 (8th Cir. 1987)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 2 (slip op. at 2).

Authority type: case; as written: United States v. Kragness, 830 F.2d 842, 847 (8th Cir. 1987); pincite: 847.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers. At 847 (before *848) the court states the facts in the light most favorable to the verdict; at 855 it quotes Turkette's 'ongoing organization' language and distinguishes enterprises from individuals who associate for the commission of sporadic crime, and lists the three characteristics of an enterprise.

Excerpt read: [at 855] An enterprise is established "by evidence of an ongoing organization, formal or informal, and by evidence that the various associates function as a continuing unit." ... distinguished from individuals who associate for the commission of sporadic crime.

- https://www.courtlistener.com/opinion/8963470/united-states-v-kragness/

### Second check: not required


## KEHOE-011: 18 U.S.C. § 1962(c)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: 18 U.S.C. § 1962(c); pincite: .

Cited for: RICO substantive prohibition

Quotes: ["for any person . . . associated with any enterprise engaged in, or the activities of which affect, interstate or foreign commerce, to conduct or participate, directly or indirectly, in the conduct of such enterprise's affairs through a pattern of racketeering activity . . . ."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; Kehoe's ellipsis quotation matches the current text of § 1962(c); the version in force at the 2002 decision was not separately retrieved.

Excerpt read: (c) It shall be unlawful for any person employed by or associated with any enterprise engaged in, or the activities of which affect, interstate or foreign commerce, to conduct or participate, directly or indirectly, in the conduct of such enterprise's affairs through a pattern of racketeering activity or collection of unlawful debt.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-012: 18 U.S.C. § 1962(c)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: § 1962(c); pincite: .

Cited for: Substantive RICO offense

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; Kehoe's ellipsis quotation matches the current text of § 1962(c); the version in force at the 2002 decision was not separately retrieved.

Excerpt read: (c) It shall be unlawful for any person employed by or associated with any enterprise engaged in, or the activities of which affect, interstate or foreign commerce, to conduct or participate, directly or indirectly, in the conduct of such enterprise's affairs through a pattern of racketeering activity or collection of unlawful debt.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-013: 18 U.S.C. § 1962(d)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: § 1962(d); pincite: .

Cited for: RICO conspiracy is a separate offense

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1962(d) makes it unlawful to conspire to violate subsection (a), (b), or (c), matching Kehoe's quotation.

Excerpt read: (d) It shall be unlawful for any person to conspire to violate any of the provisions of subsection (a), (b), or (c) of this section.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-014: United States v. Turkette, 452 U.S. 576 (1981)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: United States v. Turkette, 452 U.S. 576, 583 (1981); pincite: 583.

Cited for: RICO requires proof of enterprise and pattern

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; between the *583 and *584 markers the Court explains that enterprise and pattern are separate elements and that the enterprise is proved by evidence of an ongoing organization functioning as a continuing unit.

Excerpt read: The former is proved by evidence of an ongoing organization, formal or informal, and by evidence that the various associates function as a continuing unit. The latter is proved by evidence of the requisite number of acts of racketeering

- https://www.courtlistener.com/opinion/110529/united-states-v-turkette/

### Second check: not required


## KEHOE-015: 18 U.S.C. § 1961(4)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: 18 U.S.C. § 1961(4); pincite: .

Cited for: Definition of enterprise

Quotes: ['any individual, partnership, corporation, association, or other legal entity, and any union or group of individuals associated in fact although not a legal entity.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; definition of 'enterprise' matches Kehoe's quotation.

Excerpt read: "enterprise" includes any individual, partnership, corporation, association, or other legal entity, and any union or group of individuals associated in fact although not a legal entity;

- https://www.law.cornell.edu/uscode/text/18/1961

### Second check: not required


## KEHOE-016: United States v. Turkette, 452 U.S. 576 (1981)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 5 (slip op. at 5).

Authority type: case; as written: Turkette, 452 U.S. at 583; pincite: 583.

Cited for: Same definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; between the *583 and *584 markers the Court explains that enterprise and pattern are separate elements and that the enterprise is proved by evidence of an ongoing organization functioning as a continuing unit.

Excerpt read: The former is proved by evidence of an ongoing organization, formal or informal, and by evidence that the various associates function as a continuing unit. The latter is proved by evidence of the requisite number of acts of racketeering

- https://www.courtlistener.com/opinion/110529/united-states-v-turkette/

### Second check: not required


## KEHOE-017: 18 U.S.C. § 1961(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: 18 U.S.C. § 1961(1); pincite: .

Cited for: Definition of racketeering activity

Quotes: ['any act or threat involving murder, kidnapping, . . . robbery, bribery . . . which is chargeable under State law and punishable by imprisonment for more than one year . . . .']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII; Kehoe's ellipsis quotation of § 1961(1)(A) matches. The current text includes 'or listed chemical' after the quoted words (beyond the ellipsis); the version in force in 2002 was not separately retrieved.

Excerpt read: "racketeering activity" means (A) any act or threat involving murder, kidnapping, gambling, arson, robbery, bribery, extortion, dealing in obscene matter, or dealing in a controlled substance or listed chemical ..., which is chargeable under State law and punishable by imprisonment for more than one year;

- https://www.law.cornell.edu/uscode/text/18/1961

### Second check: not required


## KEHOE-018: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 6 (slip op. at 6).

Authority type: constitution; as written: Double Jeopardy Clause of the Fifth Amendment; pincite: .

Cited for: Kehoe's double jeopardy argument

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## KEHOE-019: United States v. Harmon, 194 F.3d 890 (8th Cir. 1999)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 6 (slip op. at 6).

Authority type: case; as written: United States v. Harmon, 194 F.3d 890, 892 (8th Cir. 1999); pincite: 892.

Cited for: Sufficiency standard

Quotes: ['the evidence in the light most favorable to the verdict and accept as established all reasonable inferences supporting the verdict.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted sufficiency standard appears near the start of the analysis (consistent with 892; page marker not separately checked).

Excerpt read: we look at the evidence in the light most favorable to the verdict and accept as established all reasonable inferences supporting the verdict.

- https://www.courtlistener.com/opinion/766527/united-states-v-daniel-harmon-jr-and-roger-c-walls/

### Second check: not required


## KEHOE-020: United States v. Frayer, 9 F.3d 1367 (8th Cir. 1993)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 6 (slip op. at 6).

Authority type: case; as written: Id. (quoting United States v. Frayer, 9 F.3d 1367, 1371 (8th Cir. 1993)); pincite: 1371.

Cited for: Reverse only if no reasonable jury could convict

Quotes: ['no reasonable jury could have found the defendant guilty beyond a reasonable doubt.']

Context: Id. resolves to Harmon, which quotes Frayer; Harmon's role is covered by the preceding record.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; after the *1371 marker the court states that an appellate court can reverse only if no reasonable jury could have found the defendant guilty beyond a reasonable doubt.

Excerpt read: An appellate court can reverse only if no reasonable jury could have found the defendant guilty beyond a reasonable doubt.

- https://www.courtlistener.com/opinion/7027222/united-states-v-frayer/

### Second check: not required


## KEHOE-021: United States v. Kragness, 830 F.2d 842 (8th Cir. 1987)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 6 (slip op. at 6).

Authority type: case; as written: United States v. Kragness, 830 F.2d 842, 855 (8th Cir. 1987); pincite: 855.

Cited for: Enterprise established by ongoing organization functioning as continuing unit

Quotes: ["enterprise is established 'by evidence of an ongoing organization, formal or informal, and by evidence that the various associates function as a continuing unit.'"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers. At 847 (before *848) the court states the facts in the light most favorable to the verdict; at 855 it quotes Turkette's 'ongoing organization' language and distinguishes enterprises from individuals who associate for the commission of sporadic crime, and lists the three characteristics of an enterprise.

Excerpt read: [at 855] An enterprise is established "by evidence of an ongoing organization, formal or informal, and by evidence that the various associates function as a continuing unit." ... distinguished from individuals who associate for the commission of sporadic crime.

- https://www.courtlistener.com/opinion/8963470/united-states-v-kragness/

### Second check: not required


## KEHOE-022: United States v. Turkette, 452 U.S. 576 (1981)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 6 (slip op. at 6).

Authority type: case; as written: quoting Turkette, 452 U.S. at 583 (1981); pincite: 583.

Cited for: Source of the enterprise language

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; between the *583 and *584 markers the Court explains that enterprise and pattern are separate elements and that the enterprise is proved by evidence of an ongoing organization functioning as a continuing unit.

Excerpt read: The former is proved by evidence of an ongoing organization, formal or informal, and by evidence that the various associates function as a continuing unit. The latter is proved by evidence of the requisite number of acts of racketeering

- https://www.courtlistener.com/opinion/110529/united-states-v-turkette/

### Second check: not required


## KEHOE-023: United States v. Kragness, 830 F.2d 842 (8th Cir. 1987)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 6 (slip op. at 6).

Authority type: case; as written: Id. [Kragness, 830 F.2d at 855]; pincite: 855.

Cited for: Enterprise distinguished from individuals who associate for sporadic crime

Quotes: ['individuals who associate [to commit] sporadic crime.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers. At 847 (before *848) the court states the facts in the light most favorable to the verdict; at 855 it quotes Turkette's 'ongoing organization' language and distinguishes enterprises from individuals who associate for the commission of sporadic crime, and lists the three characteristics of an enterprise.

Excerpt read: [at 855] An enterprise is established "by evidence of an ongoing organization, formal or informal, and by evidence that the various associates function as a continuing unit." ... distinguished from individuals who associate for the commission of sporadic crime.

- https://www.courtlistener.com/opinion/8963470/united-states-v-kragness/

### Second check: not required


## KEHOE-024: Diamonds Plus, Inc. v. Kolber, 960 F.2d 765 (8th Cir. 1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 6 (slip op. at 6).

Authority type: case; as written: Diamonds Plus, Inc. v. Kolber, 960 F.2d 765, 769 (8th Cir. 1992); pincite: 769.

Cited for: Enterprise members share a common purpose

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the three-characteristic enterprise test (common purpose, continuity of structure and personnel, ascertainable structure distinct from the pattern) straddles the *770 marker, matching 769 and 769-70.

Excerpt read: "that a RICO enterprise must exhibit three basic characteristics: (1) a common or shared purpose; (2) some continuity of structure and personnel; and (3) an ascertainable structure distinct from [*770] that inherent in a pattern of racketeering."

- https://www.courtlistener.com/opinion/580784/diamonds-plus-inc-v-larry-kolber-the-mike-james-mortgage-company-michael/

### Second check: not required


## KEHOE-025: Diamonds Plus, Inc. v. Kolber, 960 F.2d 765 (8th Cir. 1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 7 (slip op. at 7).

Authority type: case; as written: Id. [Diamonds Plus]; pincite: 769.

Cited for: Continuity of personnel

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the three-characteristic enterprise test (common purpose, continuity of structure and personnel, ascertainable structure distinct from the pattern) straddles the *770 marker, matching 769 and 769-70.

Excerpt read: "that a RICO enterprise must exhibit three basic characteristics: (1) a common or shared purpose; (2) some continuity of structure and personnel; and (3) an ascertainable structure distinct from [*770] that inherent in a pattern of racketeering."

- https://www.courtlistener.com/opinion/580784/diamonds-plus-inc-v-larry-kolber-the-mike-james-mortgage-company-michael/

### Second check: not required


## KEHOE-026: Diamonds Plus, Inc. v. Kolber, 960 F.2d 765 (8th Cir. 1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 7 (slip op. at 7).

Authority type: case; as written: Id. at 769-70; pincite: 769-70.

Cited for: Ascertainable structure distinct from pattern

Quotes: ['an ascertainable structure [exists, which is] distinct from that inherent in the pattern of racketeering.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the three-characteristic enterprise test (common purpose, continuity of structure and personnel, ascertainable structure distinct from the pattern) straddles the *770 marker, matching 769 and 769-70.

Excerpt read: "that a RICO enterprise must exhibit three basic characteristics: (1) a common or shared purpose; (2) some continuity of structure and personnel; and (3) an ascertainable structure distinct from [*770] that inherent in a pattern of racketeering."

- https://www.courtlistener.com/opinion/580784/diamonds-plus-inc-v-larry-kolber-the-mike-james-mortgage-company-michael/

### Second check: not required


## KEHOE-027: United States v. Turkette, 452 U.S. 576 (1981)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 7 (slip op. at 7).

Authority type: case; as written: see also Turkette, 452 U.S. at 583; pincite: 583.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; between the *583 and *584 markers the Court explains that enterprise and pattern are separate elements and that the enterprise is proved by evidence of an ongoing organization functioning as a continuing unit.

Excerpt read: The former is proved by evidence of an ongoing organization, formal or informal, and by evidence that the various associates function as a continuing unit. The latter is proved by evidence of the requisite number of acts of racketeering

- https://www.courtlistener.com/opinion/110529/united-states-v-turkette/

### Second check: not required


## KEHOE-028: United States v. Kragness, 830 F.2d 842 (8th Cir. 1987)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 7 (slip op. at 7).

Authority type: case; as written: Kragness, 830 F.2d at 855; pincite: 855.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers. At 847 (before *848) the court states the facts in the light most favorable to the verdict; at 855 it quotes Turkette's 'ongoing organization' language and distinguishes enterprises from individuals who associate for the commission of sporadic crime, and lists the three characteristics of an enterprise.

Excerpt read: [at 855] An enterprise is established "by evidence of an ongoing organization, formal or informal, and by evidence that the various associates function as a continuing unit." ... distinguished from individuals who associate for the commission of sporadic crime.

- https://www.courtlistener.com/opinion/8963470/united-states-v-kragness/

### Second check: not required


## KEHOE-029: United States v. Bledsoe, 674 F.2d 647 (8th Cir. 1982)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 7 (slip op. at 7).

Authority type: case; as written: United States v. Bledsoe, 674 F.2d 647, 665 (8th Cir. 1982); pincite: 665.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Bledsoe states that an enterprise must have an ascertainable structure distinct from that inherent in the pattern of racketeering (page marker not separately checked; Kragness cites Bledsoe at 664-65 for the same discussion).

Excerpt read: Finally, an enterprise must have an "ascertainable structure" distinct from that inherent in the conduct of a pattern of racketeering activity.

- https://www.courtlistener.com/opinion/8925413/united-states-v-bledsoe/

### Second check: not required


## KEHOE-030: 18 U.S.C. § 1962(c)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 8 (slip op. at 8).

Authority type: statute; as written: 18 U.S.C. § 1962(c); pincite: .

Cited for: Substantive RICO offense in double jeopardy argument

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; Kehoe's ellipsis quotation matches the current text of § 1962(c); the version in force at the 2002 decision was not separately retrieved.

Excerpt read: (c) It shall be unlawful for any person employed by or associated with any enterprise engaged in, or the activities of which affect, interstate or foreign commerce, to conduct or participate, directly or indirectly, in the conduct of such enterprise's affairs through a pattern of racketeering activity or collection of unlawful debt.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-031: 18 U.S.C. § 1962(d)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 8 (slip op. at 8).

Authority type: statute; as written: § 1962(d); pincite: .

Cited for: RICO conspiracy in double jeopardy argument

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1962(d) makes it unlawful to conspire to violate subsection (a), (b), or (c), matching Kehoe's quotation.

Excerpt read: (d) It shall be unlawful for any person to conspire to violate any of the provisions of subsection (a), (b), or (c) of this section.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-032: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 8 (slip op. at 8).

Authority type: constitution; as written: Double Jeopardy Clause of the Fifth Amendment; pincite: .

Cited for: Kehoe's argument

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## KEHOE-033: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 8 (slip op. at 8).

Authority type: constitution; as written: The Double Jeopardy Clause; pincite: .

Cited for: Protects against successive prosecutions and multiple punishments

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## KEHOE-034: United States v. Bennett, 44 F.3d 1364 (8th Cir. 1995)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: United States v. Bennett, 44 F.3d 1364, 1368 (8th Cir. 1995); pincite: 1368.

Cited for: Double jeopardy protections

Quotes: ['both successive prosecutions and multiple punishments for the same criminal offense.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text. Early in the double jeopardy discussion (consistent with 1368) Bennett states the clause protects against successive prosecutions and multiple punishments, citing Pearce; later (consistent with 1375) it quotes the 'axiomatic that a substantive offense is distinct from a conspiracy' sentence from Phillips. Page markers not separately checked.

Excerpt read: Under this clause, a defendant is protected from both successive prosecutions and multiple punishments for the same criminal offense. ... "[a] RICO substantive charge is not a conspiracy and it is axiomatic that a substantive offense is distinct from a conspiracy to commit that or another substantive offense."

- https://www.courtlistener.com/opinion/7031268/united-states-v-bennett/

### Second check: not required


## KEHOE-035: North Carolina v. Pearce, 395 U.S. 711 (1969)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: citing North Carolina v. Pearce, 395 U.S. 711, 717 (1969); pincite: 717.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; at 717 the Court lists the double jeopardy protections, including against a second prosecution after conviction and multiple punishments for the same offense.

Excerpt read: It protects against a second prosecution for the same offense after conviction. And it protects against multiple punishments for the same offense.

- https://www.courtlistener.com/opinion/107978/north-carolina-v-pearce/

### Second check: not required


## KEHOE-036: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 8 (slip op. at 8).

Authority type: constitution; as written: a violation of the Double Jeopardy Clause; pincite: .

Cited for: Same-offense requirement

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## KEHOE-037: United States v. Bennett, 44 F.3d 1364 (8th Cir. 1995)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: Id. (citation omitted) [Bennett]; pincite: 1368.

Cited for: Defendant must prove offenses are the same in law and fact

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text. Early in the double jeopardy discussion (consistent with 1368) Bennett states the clause protects against successive prosecutions and multiple punishments, citing Pearce; later (consistent with 1375) it quotes the 'axiomatic that a substantive offense is distinct from a conspiracy' sentence from Phillips. Page markers not separately checked.

Excerpt read: Under this clause, a defendant is protected from both successive prosecutions and multiple punishments for the same criminal offense. ... "[a] RICO substantive charge is not a conspiracy and it is axiomatic that a substantive offense is distinct from a conspiracy to commit that or another substantive offense."

- https://www.courtlistener.com/opinion/7031268/united-states-v-bennett/

### Second check: not required


## KEHOE-038: Blockburger v. United States, 284 U.S. 299 (1932)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: Blockburger v. United States, 284 U.S. 299, 304 (1931); pincite: 304.

Cited for: Same-elements test

Quotes: ['each of the offenses . . . requires proof of a different element.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted 'requires proof of a different element' language and the same-elements test appear at 304. Kehoe's '(1931)' reflects the December 1931 decision date that the reporter citation dates to 1932; consistent with common citation practice.

Excerpt read: ... each of the offenses created requires proof of a different element. The applicable rule is that ... the test ... is whether each provision requires proof of a fact which the other does not.

- https://www.courtlistener.com/opinion/101824/blockburger-v-united-states/

### Second check: not required


## KEHOE-039: United States v. Dixon, 509 U.S. 688 (1993)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: United States v. Dixon, 509 U.S. 688, 696-97 (1993); pincite: 696-97.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the same-elements (Blockburger) discussion spans 696-97 (the *697 marker appears within it).

Excerpt read: where the two offenses for which the defendant is punished or tried cannot survive the "same-elements" test, the double jeopardy bar applies.

- https://www.courtlistener.com/opinion/112906/united-states-v-dixon/

### Second check: not required


## KEHOE-040: 18 U.S.C. § 1962(c)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: statute; as written: Section 1962(c); pincite: .

Cited for: Creates substantive RICO offense

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; Kehoe's ellipsis quotation matches the current text of § 1962(c); the version in force at the 2002 decision was not separately retrieved.

Excerpt read: (c) It shall be unlawful for any person employed by or associated with any enterprise engaged in, or the activities of which affect, interstate or foreign commerce, to conduct or participate, directly or indirectly, in the conduct of such enterprise's affairs through a pattern of racketeering activity or collection of unlawful debt.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-041: 18 U.S.C. § 1962(d)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: statute; as written: § 1962(d); pincite: .

Cited for: Conspiracy prohibition

Quotes: ['for any person to conspire to violate any of the provisions of subsection . . . (c) . . . .']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1962(d) makes it unlawful to conspire to violate subsection (a), (b), or (c), matching Kehoe's quotation.

Excerpt read: (d) It shall be unlawful for any person to conspire to violate any of the provisions of subsection (a), (b), or (c) of this section.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-042: 18 U.S.C. § 1962(c)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: statute; as written: 18 U.S.C. §§ 1962(c); pincite: .

Cited for: Citation for the two provisions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; Kehoe's ellipsis quotation matches the current text of § 1962(c); the version in force at the 2002 decision was not separately retrieved.

Excerpt read: (c) It shall be unlawful for any person employed by or associated with any enterprise engaged in, or the activities of which affect, interstate or foreign commerce, to conduct or participate, directly or indirectly, in the conduct of such enterprise's affairs through a pattern of racketeering activity or collection of unlawful debt.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-043: 18 U.S.C. § 1962(d)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: statute; as written: [§§ 1962] (d); pincite: .

Cited for: Citation for the two provisions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1962(d) makes it unlawful to conspire to violate subsection (a), (b), or (c), matching Kehoe's quotation.

Excerpt read: (d) It shall be unlawful for any person to conspire to violate any of the provisions of subsection (a), (b), or (c) of this section.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-044: 18 U.S.C. § 1962(d)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: statute; as written: § 1962(d); pincite: .

Cited for: RICO conspiracy requires additional evidence

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1962(d) makes it unlawful to conspire to violate subsection (a), (b), or (c), matching Kehoe's quotation.

Excerpt read: (d) It shall be unlawful for any person to conspire to violate any of the provisions of subsection (a), (b), or (c) of this section.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-045: 18 U.S.C. § 1962(c)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: statute; as written: § 1962(c); pincite: .

Cited for: Right to relief under substantive provision

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; Kehoe's ellipsis quotation matches the current text of § 1962(c); the version in force at the 2002 decision was not separately retrieved.

Excerpt read: (c) It shall be unlawful for any person employed by or associated with any enterprise engaged in, or the activities of which affect, interstate or foreign commerce, to conduct or participate, directly or indirectly, in the conduct of such enterprise's affairs through a pattern of racketeering activity or collection of unlawful debt.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-046: Handeen v. Lemaire, 112 F.3d 1339 (8th Cir. 1997)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: Handeen v. Lemaire, 112 F.3d 1339, 1354-55 (8th Cir. 1997); pincite: 1354-55.

Cited for: Additional evidence of agreement shows RICO conspiracy

Quotes: ['When a plaintiff has already established a right to relief under § 1962(c), he may show a conspiracy to violate RICO simply by presenting additional evidence that the defendant entered into an agreement to breach the statute.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the first quotation straddles the *1355 marker (1354-55) and the 'tacit understanding' quotation follows at 1355 (Handeen quoting Darden).

Excerpt read: When a plaintiff has already established a right to relief under § 1962(c), he may show a conspiracy to violate RICO simply by presenting additional evidence that the defendant entered into an agreement to breach the stat[*1355]ute. ... "need only establish a tacit understanding between the parties, and this may be shown wholly through the circumstantial evidence of [each defendant's] actions."

- https://www.courtlistener.com/opinion/740403/paul-handeen-v-gregory-a-lemaire-henry-lemaire-patricia-lemaire-orlins/

### Second check: not required


## KEHOE-047: Handeen v. Lemaire, 112 F.3d 1339 (8th Cir. 1997)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: Id. at 1355 (citation omitted); pincite: 1355.

Cited for: Tacit understanding suffices

Quotes: ["need only establish a tacit understanding between the parties, and . . . may be shown wholly through the circumstantial evidence of [each defendant's] actions."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the first quotation straddles the *1355 marker (1354-55) and the 'tacit understanding' quotation follows at 1355 (Handeen quoting Darden).

Excerpt read: When a plaintiff has already established a right to relief under § 1962(c), he may show a conspiracy to violate RICO simply by presenting additional evidence that the defendant entered into an agreement to breach the stat[*1355]ute. ... "need only establish a tacit understanding between the parties, and this may be shown wholly through the circumstantial evidence of [each defendant's] actions."

- https://www.courtlistener.com/opinion/740403/paul-handeen-v-gregory-a-lemaire-henry-lemaire-patricia-lemaire-orlins/

### Second check: not required


## KEHOE-048: 18 U.S.C. § 1962(c)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: statute; as written: 18 U.S.C. §§ 1962(c) [and (d)]; pincite: .

Cited for: Offenses prescribed

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; Kehoe's ellipsis quotation matches the current text of § 1962(c); the version in force at the 2002 decision was not separately retrieved.

Excerpt read: (c) It shall be unlawful for any person employed by or associated with any enterprise engaged in, or the activities of which affect, interstate or foreign commerce, to conduct or participate, directly or indirectly, in the conduct of such enterprise's affairs through a pattern of racketeering activity or collection of unlawful debt.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-049: 18 U.S.C. § 1962(d)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: statute; as written: [§§ 1962(c)] and (d); pincite: .

Cited for: Offenses prescribed

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1962(d) makes it unlawful to conspire to violate subsection (a), (b), or (c), matching Kehoe's quotation.

Excerpt read: (d) It shall be unlawful for any person to conspire to violate any of the provisions of subsection (a), (b), or (c) of this section.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-050: United States v. Felix, 503 U.S. 378 (1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: United States v. Felix, 503 U.S. 378, 389 (1992); pincite: 389.

Cited for: Substantive crime and conspiracy not the same offense

Quotes: ["[a] substantive crime and a conspiracy to commit that crime are not the 'same offense' for double jeopardy purposes."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the Court states the long-standing rule that a substantive crime and a conspiracy to commit it are not the 'same offence' for double jeopardy purposes. Kehoe's quotation modernizes 'offence' to 'offense'; pin page not separately checked.

Excerpt read: is the rule that a substantive crime and a conspiracy to commit that crime are not the "same offence" for double jeopardy purposes.

- https://www.courtlistener.com/opinion/112713/united-states-v-felix/

### Second check: not required


## KEHOE-051: United States v. Miller, 995 F.2d 865 (8th Cir. 1993)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: United States v. Miller, 995 F.2d 865, 868 (8th Cir. 1993); pincite: 868.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Miller quotes Felix that a substantive crime and a conspiracy to commit it are not the same offense for double jeopardy purposes.

Excerpt read: the Supreme Court reaffirmed the rule that "a substantive crime, and a conspiracy to commit that crime, are not the 'same offense' for double jeopardy purposes."

- https://www.courtlistener.com/opinion/608932/united-states-v-donald-lee-miller-united-states-of-america-v-bruce-alden/

### Second check: not required


## KEHOE-052: United States v. Bennett, 44 F.3d 1364 (8th Cir. 1995)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: Bennett, 44 F.3d at 1375; pincite: 1375.

Cited for: RICO substantive charge distinct from conspiracy

Quotes: ['[A] RICO substantive charge is not a conspiracy and it is axiomatic that a substantive offense is distinct from a conspiracy to commit that or another substantive offense.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text. Early in the double jeopardy discussion (consistent with 1368) Bennett states the clause protects against successive prosecutions and multiple punishments, citing Pearce; later (consistent with 1375) it quotes the 'axiomatic that a substantive offense is distinct from a conspiracy' sentence from Phillips. Page markers not separately checked.

Excerpt read: Under this clause, a defendant is protected from both successive prosecutions and multiple punishments for the same criminal offense. ... "[a] RICO substantive charge is not a conspiracy and it is axiomatic that a substantive offense is distinct from a conspiracy to commit that or another substantive offense."

- https://www.courtlistener.com/opinion/7031268/united-states-v-bennett/

### Second check: not required


## KEHOE-053: 18 U.S.C. § 1959

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: statute; as written: 18 U.S.C. § 1959; pincite: .

Cited for: Kehoe's Tenth Amendment challenge to § 1959 conviction

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1959(a) punishes violent crimes 'in violation of the laws of any State or the United States' committed for the purpose of gaining or maintaining position in a racketeering enterprise, including attempts (§ 1959(a)(5) covers attempting or conspiring to commit murder). Matches Kehoe's quotation and the prompt's description of attempted murder in aid of racketeering.

Excerpt read: ... for the purpose of gaining entrance to or maintaining or increasing position in an enterprise engaged in racketeering activity, murders, kidnaps, maims, assaults with a dangerous weapon, ... or threatens to commit a crime of violence against any individual in violation of the laws of any State or the United States, or attempts or conspires so to do, shall be punished-- ... (5) for attempting or conspiring to commit murder or kidnapping, by imprisonment for not more than ten years

- https://www.law.cornell.edu/uscode/text/18/1959

### Second check: not required


## KEHOE-054: U.S. Const. amend. X

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 9 (slip op. at 9).

Authority type: constitution; as written: the Tenth Amendment; pincite: .

Cited for: Kehoe's argument that prosecution encroached on state sovereignty

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Tenth Amendment text at Cornell LII; Kehoe references it for the state-sovereignty challenge.

Excerpt read: The powers not delegated to the United States by the Constitution, nor prohibited by it to the States, are reserved to the States respectively, or to the people.

- https://www.law.cornell.edu/constitution/tenth_amendment

### Second check: not required


## KEHOE-055: 18 U.S.C. § 1959

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: statute; as written: 18 U.S.C. § 1959; pincite: .

Cited for: Statute of conviction; incorporates state-law crimes of violence

Quotes: ['Whoever . . . for the purpose of gaining entrance to or maintaining or increasing position in an enterprise engaged in racketeering activity, murders, kidnaps . . . or threatens to commit a crime of violence against any individual in violation of the laws of any State or the United States, or attempts or conspires so to do, shall be punished . . . .']

Context: This page is the 'slip op. at 10' the assignment 1 rubric cites for state-law predicates.

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1959(a) punishes violent crimes 'in violation of the laws of any State or the United States' committed for the purpose of gaining or maintaining position in a racketeering enterprise, including attempts (§ 1959(a)(5) covers attempting or conspiring to commit murder). Matches Kehoe's quotation and the prompt's description of attempted murder in aid of racketeering.

Excerpt read: ... for the purpose of gaining entrance to or maintaining or increasing position in an enterprise engaged in racketeering activity, murders, kidnaps, maims, assaults with a dangerous weapon, ... or threatens to commit a crime of violence against any individual in violation of the laws of any State or the United States, or attempts or conspires so to do, shall be punished-- ... (5) for attempting or conspiring to commit murder or kidnapping, by imprisonment for not more than ten years

- https://www.law.cornell.edu/uscode/text/18/1959

### Second check: not required


## KEHOE-056: 18 U.S.C. § 1959

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: statute; as written: 18 U.S.C. § 1959(a); pincite: .

Cited for: Pinpoint for the quotation

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1959(a) punishes violent crimes 'in violation of the laws of any State or the United States' committed for the purpose of gaining or maintaining position in a racketeering enterprise, including attempts (§ 1959(a)(5) covers attempting or conspiring to commit murder). Matches Kehoe's quotation and the prompt's description of attempted murder in aid of racketeering.

Excerpt read: ... for the purpose of gaining entrance to or maintaining or increasing position in an enterprise engaged in racketeering activity, murders, kidnaps, maims, assaults with a dangerous weapon, ... or threatens to commit a crime of violence against any individual in violation of the laws of any State or the United States, or attempts or conspires so to do, shall be punished-- ... (5) for attempting or conspiring to commit murder or kidnapping, by imprisonment for not more than ten years

- https://www.law.cornell.edu/uscode/text/18/1959

### Second check: not required


## KEHOE-057: 18 U.S.C. § 1959

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: statute; as written: a § 1959 violation; pincite: .

Cited for: State or federal criminal violation is a requisite element

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1959(a) punishes violent crimes 'in violation of the laws of any State or the United States' committed for the purpose of gaining or maintaining position in a racketeering enterprise, including attempts (§ 1959(a)(5) covers attempting or conspiring to commit murder). Matches Kehoe's quotation and the prompt's description of attempted murder in aid of racketeering.

Excerpt read: ... for the purpose of gaining entrance to or maintaining or increasing position in an enterprise engaged in racketeering activity, murders, kidnaps, maims, assaults with a dangerous weapon, ... or threatens to commit a crime of violence against any individual in violation of the laws of any State or the United States, or attempts or conspires so to do, shall be punished-- ... (5) for attempting or conspiring to commit murder or kidnapping, by imprisonment for not more than ten years

- https://www.law.cornell.edu/uscode/text/18/1959

### Second check: not required


## KEHOE-058: United States v. Martino, 648 F.2d 367 (5th Cir. 1981)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: United States v. Martino, 648 F.2d 367, 381 (5th Cir. June 1981); pincite: 381.

Cited for: Crimes of violence are RICO predicate acts

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; in rejecting the Ninth and Tenth Amendment challenge Martino states that RICO proscribes the furthering of the enterprise, not the predicate acts, which are proscribed by existing state or federal laws.

Excerpt read: This argument ignores the essence of RICO which proscribes the furthering of the enterprise, not the predicate acts. The predicate acts are, in turn, proscribed by existing, enumerated state or federal laws.

- https://www.courtlistener.com/opinion/8923999/united-states-v-martino/

### Second check: not required


## KEHOE-059: United States v. Martino, 648 F.2d 367 (5th Cir. 1981)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: Id. [Martino]; pincite: 381.

Cited for: RICO criminalizes furthering the enterprise, not the predicate acts

Quotes: ['the furthering of the enterprise, not the predicate acts.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; in rejecting the Ninth and Tenth Amendment challenge Martino states that RICO proscribes the furthering of the enterprise, not the predicate acts, which are proscribed by existing state or federal laws.

Excerpt read: This argument ignores the essence of RICO which proscribes the furthering of the enterprise, not the predicate acts. The predicate acts are, in turn, proscribed by existing, enumerated state or federal laws.

- https://www.courtlistener.com/opinion/8923999/united-states-v-martino/

### Second check: not required


## KEHOE-060: United States v. Crosby, 20 F.3d 480 (D.C. Cir. 1994)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: Unites States v. Crosby, 20 F.3d 480, 484 (D.C. Cir. 1994); pincite: 484.

Cited for: RICO supplements existing predicate crimes

Quotes: ['RICO was enacted to supplement rather than replace the existing predicate crimes and penalties.']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener text; the quotation appears and Crosby so holds (and its double jeopardy holding matches the parenthetical). Defect: typo 'Unites States' in the court's slip opinion.

Excerpt read: indicating that RICO was enacted to supplement rather than replace the existing predicate crimes and penalties. ... Congress intended that a RICO violation be a discrete offense that can be prosecuted separately from its underlying predicate offenses.

- https://www.courtlistener.com/opinion/7028389/united-states-v-crosby/

### Second check: not required


## KEHOE-061: 18 U.S.C. § 1962(c)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: statute; as written: 18 U.S.C. §§ 1962(c) [and (d)]; pincite: .

Cited for: Crosby parenthetical

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; Kehoe's ellipsis quotation matches the current text of § 1962(c); the version in force at the 2002 decision was not separately retrieved.

Excerpt read: (c) It shall be unlawful for any person employed by or associated with any enterprise engaged in, or the activities of which affect, interstate or foreign commerce, to conduct or participate, directly or indirectly, in the conduct of such enterprise's affairs through a pattern of racketeering activity or collection of unlawful debt.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-062: 18 U.S.C. § 1962(d)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: statute; as written: [§§ 1962(c)] and (d); pincite: .

Cited for: Crosby parenthetical

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1962(d) makes it unlawful to conspire to violate subsection (a), (b), or (c), matching Kehoe's quotation.

Excerpt read: (d) It shall be unlawful for any person to conspire to violate any of the provisions of subsection (a), (b), or (c) of this section.

- https://www.law.cornell.edu/uscode/text/18/1962

### Second check: not required


## KEHOE-063: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: constitution; as written: Double Jeopardy Clause of the Fifth Amendment; pincite: .

Cited for: Crosby parenthetical

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## KEHOE-064: United States v. Carrillo, 229 F.3d 177 (2d Cir. 2000)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: United States v. Carrillo, 229 F.3d 177, 182 (2d Cir. 2000); pincite: 182.

Cited for: RICO does not incorporate elements of state crimes

Quotes: ["RICO's allusion to state crimes was not intended to incorporate elements of state crimes"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; all three quotations appear (Carrillo quoting Miller/Diaz and Coonan). Kehoe's bracketed '[under New York state law]' paraphrases the context; 'states's' tracks the source's 'states''. Pin pages not separately checked.

Excerpt read: "RICO's allusion to state crimes was not intended to incorporate elements of state crimes, but only to provide a general substantive frame of reference" ... the prior acquittal did not bar the RICO prosecution ... "'Congress did not intend to incorporate the various states' procedural and evidentiary rules into the RICO statute.'"

- https://www.courtlistener.com/opinion/7082643/united-states-v-carrillo/

### Second check: not required


## KEHOE-065: United States v. Carrillo, 229 F.3d 177 (2d Cir. 2000)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: Id. [Carrillo]; pincite: 182.

Cited for: Reference to state crimes identifies generic conduct

Quotes: ["the type of generic conduct which will serve as a RICO predicate and satisfy RICO's pattern requirement."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; all three quotations appear (Carrillo quoting Miller/Diaz and Coonan). Kehoe's bracketed '[under New York state law]' paraphrases the context; 'states's' tracks the source's 'states''. Pin pages not separately checked.

Excerpt read: "RICO's allusion to state crimes was not intended to incorporate elements of state crimes, but only to provide a general substantive frame of reference" ... the prior acquittal did not bar the RICO prosecution ... "'Congress did not intend to incorporate the various states' procedural and evidentiary rules into the RICO statute.'"

- https://www.courtlistener.com/opinion/7082643/united-states-v-carrillo/

### Second check: not required


## KEHOE-066: United States v. Coonan, 938 F.2d 1553 (2d Cir. 1991)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: quoting United States v. Coonan, 938 F.2d 1553, 1564 (2d Cir. 1991); pincite: 1564.

Cited for: Source of 'generic conduct' language

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted sentence appears just before the *1565 marker (at 1564).

Excerpt read: Rather, section 1961(1)(A) merely describes the type of generic conduct which will serve as a RICO predicate and satisfy RICO's pattern requirement.

- https://www.courtlistener.com/opinion/8999180/united-states-v-coonan/

### Second check: not required


## KEHOE-067: United States v. Crosby, 20 F.3d 480 (D.C. Cir. 1994)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: Crosby, 20 F.3d at 484; pincite: 484.

Cited for: RICO violation is discrete offense

Quotes: ['discrete offense that can be prosecuted separately from its underlying predicate offenses,']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; both quotations ('supplement rather than replace' and 'discrete offense that can be prosecuted separately') appear in the double jeopardy discussion.

Excerpt read: indicating that RICO was enacted to supplement rather than replace the existing predicate crimes and penalties. ... Congress intended that a RICO violation be a discrete offense that can be prosecuted separately from its underlying predicate offenses.

- https://www.courtlistener.com/opinion/7028389/united-states-v-crosby/

### Second check: not required


## KEHOE-068: United States v. Carrillo, 229 F.3d 177 (2d Cir. 2000)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: Carrillo, 229 F.3d at 182; pincite: 182.

Cited for: State may prosecute predicate crimes; prior acquittal no bar

Quotes: ['[A] prior acquittal [under New York state law] did not bar the RICO prosecution . . . .']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; all three quotations appear (Carrillo quoting Miller/Diaz and Coonan). Kehoe's bracketed '[under New York state law]' paraphrases the context; 'states's' tracks the source's 'states''. Pin pages not separately checked.

Excerpt read: "RICO's allusion to state crimes was not intended to incorporate elements of state crimes, but only to provide a general substantive frame of reference" ... the prior acquittal did not bar the RICO prosecution ... "'Congress did not intend to incorporate the various states' procedural and evidentiary rules into the RICO statute.'"

- https://www.courtlistener.com/opinion/7082643/united-states-v-carrillo/

### Second check: not required


## KEHOE-069: United States v. Carrillo, 229 F.3d 177 (2d Cir. 2000)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: Id. at 183; pincite: 183.

Cited for: Congress did not incorporate state procedural rules

Quotes: ["Congress did not intend to incorporate the various states's procedural and evidentiary rules into the RICO statute."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; all three quotations appear (Carrillo quoting Miller/Diaz and Coonan). Kehoe's bracketed '[under New York state law]' paraphrases the context; 'states's' tracks the source's 'states''. Pin pages not separately checked.

Excerpt read: "RICO's allusion to state crimes was not intended to incorporate elements of state crimes, but only to provide a general substantive frame of reference" ... the prior acquittal did not bar the RICO prosecution ... "'Congress did not intend to incorporate the various states' procedural and evidentiary rules into the RICO statute.'"

- https://www.courtlistener.com/opinion/7082643/united-states-v-carrillo/

### Second check: not required


## KEHOE-070: 18 U.S.C. § 1959

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 10 (slip op. at 10).

Authority type: statute; as written: RICO and § 1959; pincite: .

Cited for: Do not encroach on state sovereignty

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; § 1959(a) punishes violent crimes 'in violation of the laws of any State or the United States' committed for the purpose of gaining or maintaining position in a racketeering enterprise, including attempts (§ 1959(a)(5) covers attempting or conspiring to commit murder). Matches Kehoe's quotation and the prompt's description of attempted murder in aid of racketeering.

Excerpt read: ... for the purpose of gaining entrance to or maintaining or increasing position in an enterprise engaged in racketeering activity, murders, kidnaps, maims, assaults with a dangerous weapon, ... or threatens to commit a crime of violence against any individual in violation of the laws of any State or the United States, or attempts or conspires so to do, shall be punished-- ... (5) for attempting or conspiring to commit murder or kidnapping, by imprisonment for not more than ten years

- https://www.law.cornell.edu/uscode/text/18/1959

### Second check: not required


## KEHOE-071: U.S. Const. amend. X

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 11 (slip op. at 11).

Authority type: constitution; as written: do not violate the Tenth Amendment; pincite: .

Cited for: Holding

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Tenth Amendment text at Cornell LII; Kehoe references it for the state-sovereignty challenge.

Excerpt read: The powers not delegated to the United States by the Constitution, nor prohibited by it to the States, are reserved to the States respectively, or to the people.

- https://www.law.cornell.edu/constitution/tenth_amendment

### Second check: not required


## KEHOE-072: United States v. Martino, 648 F.2d 367 (5th Cir. 1981)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: See Martino, 648 F.3d at 381; pincite: 381.

Cited for: Rejecting Ninth and Tenth Amendment challenges to RICO

Quotes: []

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

The short form gives the reporter as F.3d; Martino is reported at 648 F.2d 367 (the full citation on the preceding page of the slip). 648 F.3d 381 would be a different (2011) volume. Read Martino on CourtListener: it rejects the Ninth/Tenth Amendment argument, so the proposition is supported; the reporter series is garbled in the court's slip opinion. The reporter version of Kehoe on CourtListener reads '648 F.2d at 381'.

Excerpt read: This argument ignores the essence of RICO which proscribes the furthering of the enterprise, not the predicate acts. The predicate acts are, in turn, proscribed by existing, enumerated state or federal laws.

- https://www.courtlistener.com/opinion/8923999/united-states-v-martino/

### Second check: pending


## KEHOE-073: U.S. Const. amend. IX

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 11 (slip op. at 11).

Authority type: constitution; as written: Ninth [Amendment] (in Martino parenthetical); pincite: .

Cited for: Challenge rejected in Martino

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Ninth Amendment text at Cornell LII.

Excerpt read: The enumeration in the Constitution, of certain rights, shall not be construed to deny or disparage others retained by the people.

- https://www.law.cornell.edu/constitution/ninth_amendment

### Second check: not required


## KEHOE-074: U.S. Const. amend. X

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 11 (slip op. at 11).

Authority type: constitution; as written: [Ninth and] Tenth Amendments (in Martino parenthetical); pincite: .

Cited for: Challenge rejected in Martino

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Tenth Amendment text at Cornell LII; Kehoe references it for the state-sovereignty challenge.

Excerpt read: The powers not delegated to the United States by the Constitution, nor prohibited by it to the States, are reserved to the States respectively, or to the people.

- https://www.law.cornell.edu/constitution/tenth_amendment

### Second check: not required


## KEHOE-075: Ark. Code Ann. § 5-10-102(a)(2) (1987)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF pages 11-12, footnote 3 (slip op. at 11 n.3).

Authority type: statute; as written: Section 5-10-102(a)(2) of the Arkansas Code of 1987; pincite: (a)(2).

Cited for: First-degree murder definition as quoted in Jury Instruction No. 19

Quotes: ['A person commits murder in the first degree if, with a purpose of causing the death of another person, he causes the death of another person.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Arkansas Code text could not be fetched from Justia (HTTP 403). Read the statute's text as quoted in Walker v. State, 324 Ark. 106, 918 S.W.2d 172 (1996) (Repl. 1993), on CourtListener; it matches the jury instruction quoted in Kehoe n.3.

Excerpt read: "A person commits Murder in the First Degree if, with a purpose of causing the death of another person, he causes the death of another person." Ark. Code Ann. § 5-10-102(a)(2) (Repl. 1993).

- https://www.courtlistener.com/opinion/2417480/walker-v-state/

### Second check: not required


## KEHOE-076: United States v. Finch, 16 F.3d 228 (8th Cir. 1994)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: United States v. Finch, 16 F.3d 228, 230 (8th Cir. 1994); pincite: 230.

Cited for: Consistency of verdicts not necessary

Quotes: ["[i]t is well established that consistency of a jury's verdicts is not necessary."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers: the consistency sentence (citing Dunn) is at 230, the compromise quotation (from Dunn) straddles *231, and the jury-irrationality sentence (quoting Powell) is at 231.

Excerpt read: It is well established that consistency of a jury's verdicts is not necessary. ... "That the verdict may have been the result of compromise, or of a mistake on the part of the jury, is possible. But verdicts cannot be upset by speculation or inquiry into such [*231] matters." ... "is afforded protection against jury irrationality or error by the independent review of the sufficiency of the evidence"

- https://www.courtlistener.com/opinion/662506/united-states-v-lynn-m-finch/

### Second check: not required


## KEHOE-077: Dunn v. United States, 284 U.S. 390 (1932)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: citing Dunn v. United States, 284 U.S. 390, 393 (1932); pincite: 393.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Dunn holds consistency in verdicts is not necessary (393) and the compromise sentence follows the *394 marker.

Excerpt read: [*394] That the verdict may have been the result of compromise, or of a mistake on the part of the jury, is possible. But verdicts cannot be upset by speculation or inquiry into such matters.

- https://www.courtlistener.com/opinion/101833/dunn-v-united-states/

### Second check: not required


## KEHOE-078: Lowenfield v. Phelps, 484 U.S. 231 (1988)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: See Lowenfield v. Phelps, 484 U.S. 231, 241 (1988); pincite: 241.

Cited for: Sentencing-phase findings intended to be narrow

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener text. At 241 the Court only frames the petitioner's argument that the sentencing phase did not further narrow the death-eligible class; the discussion of the narrowing function performed at the guilt or sentencing phase is at 244-46. The 'See' cite supports the general idea that capital sentencing findings serve a narrowing function, but Kehoe's paraphrase ('intended to be narrow') is loose and the pin is to the argument rather than the holding.

Excerpt read: Petitioner urges that this overlap left the jury at the sentencing phase free merely to repeat one of its findings in the guilt phase, and thus not to narrow further in the sentencing phase the class of death-eligible murderers. ... We see no reason why this narrowing function may not be [*245] performed by jury findings at either the sentencing phase of the trial or the guilt phase.

- https://www.courtlistener.com/opinion/111978/lowenfield-v-phelps/

### Second check: not required


## KEHOE-079: United States v. Finch, 16 F.3d 228 (8th Cir. 1994)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: Finch, 16 F.3d at 230-31; pincite: 230-31.

Cited for: Inconsistency may reflect compromise; verdicts not upset by speculation

Quotes: ['[I]t may have been the result of compromise, or of a mistake on the part of the jury . . . . But verdicts cannot be upset by speculation or inquiry into such matters.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers: the consistency sentence (citing Dunn) is at 230, the compromise quotation (from Dunn) straddles *231, and the jury-irrationality sentence (quoting Powell) is at 231.

Excerpt read: It is well established that consistency of a jury's verdicts is not necessary. ... "That the verdict may have been the result of compromise, or of a mistake on the part of the jury, is possible. But verdicts cannot be upset by speculation or inquiry into such [*231] matters." ... "is afforded protection against jury irrationality or error by the independent review of the sufficiency of the evidence"

- https://www.courtlistener.com/opinion/662506/united-states-v-lynn-m-finch/

### Second check: not required


## KEHOE-080: Dunn v. United States, 284 U.S. 390 (1932)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: citing Dunn, 284 U.S. at 394; pincite: 394.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Dunn holds consistency in verdicts is not necessary (393) and the compromise sentence follows the *394 marker.

Excerpt read: [*394] That the verdict may have been the result of compromise, or of a mistake on the part of the jury, is possible. But verdicts cannot be upset by speculation or inquiry into such matters.

- https://www.courtlistener.com/opinion/101833/dunn-v-united-states/

### Second check: not required


## KEHOE-081: United States v. Finch, 16 F.3d 228 (8th Cir. 1994)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: As we noted in Finch; pincite: .

Cited for: Protection via sufficiency review

Quotes: []

Context: Bare case-name reference.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers: the consistency sentence (citing Dunn) is at 230, the compromise quotation (from Dunn) straddles *231, and the jury-irrationality sentence (quoting Powell) is at 231.

Excerpt read: It is well established that consistency of a jury's verdicts is not necessary. ... "That the verdict may have been the result of compromise, or of a mistake on the part of the jury, is possible. But verdicts cannot be upset by speculation or inquiry into such [*231] matters." ... "is afforded protection against jury irrationality or error by the independent review of the sufficiency of the evidence"

- https://www.courtlistener.com/opinion/662506/united-states-v-lynn-m-finch/

### Second check: not required


## KEHOE-082: United States v. Finch, 16 F.3d 228 (8th Cir. 1994)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF pages 12-13 (slip op. at 12-13).

Authority type: case; as written: Id. at 231; pincite: 231.

Cited for: Protection against jury irrationality

Quotes: ['is afforded protection against jury irrationality or error by the independent review of the sufficiency of the evidence.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers: the consistency sentence (citing Dunn) is at 230, the compromise quotation (from Dunn) straddles *231, and the jury-irrationality sentence (quoting Powell) is at 231.

Excerpt read: It is well established that consistency of a jury's verdicts is not necessary. ... "That the verdict may have been the result of compromise, or of a mistake on the part of the jury, is possible. But verdicts cannot be upset by speculation or inquiry into such [*231] matters." ... "is afforded protection against jury irrationality or error by the independent review of the sufficiency of the evidence"

- https://www.courtlistener.com/opinion/662506/united-states-v-lynn-m-finch/

### Second check: not required


## KEHOE-083: United States v. Powell, 469 U.S. 57 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: citing United States v. Powell, 469 U.S. 57, 67 (1984); pincite: 67.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the Court notes the defendant is protected against jury irrationality by independent sufficiency review (consistent with 67; page marker not separately checked).

Excerpt read: a criminal defendant already is afforded protection against jury irrationality or error by the independent review of the sufficiency of the evidence undertaken by the trial and appellate courts.

- https://www.courtlistener.com/opinion/111286/united-states-v-powell/

### Second check: not required


## KEHOE-084: Blair v. Armontrout, 916 F.2d 1310 (8th Cir. 1990)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: See Blair v. Armontrout, 916 F.2d 1310, 1333 (8th Cir. 1990); pincite: 1333.

Cited for: Walling off attorney prevents disqualification

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the court explains that a screening mechanism or 'Chinese Wall' can avoid disqualifying an entire prosecuting office (pin not separately checked).

Excerpt read: we believe that a screening mechanism or Chinese Wall could be implemented to avoid disqualifying the entire Attorney General's office.

- https://www.courtlistener.com/opinion/550152/walter-j-blair-v-bill-armontrout-walter-j-blair-v-bill-armontrout/

### Second check: not required


## KEHOE-085: Fred Weber, Inc. v. Shell Oil Co., 566 F.2d 602 (8th Cir. 1977)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: Fred Weber, Inc. v. Shell Oil Co., 566 F.2d 602, 605-06 (8th Cir. 1977); pincite: 605-06.

Cited for: Disqualification reviewed for abuse of discretion

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; a district court's disqualification ruling is discretionary and upset only for abuse of discretion (pin not separately checked).

Excerpt read: The dispatch of this duty is discretionary in nature and the finding of the district court will be upset only upon a showing that an abuse of discretion has taken place.

- https://www.courtlistener.com/opinion/350940/fred-weber-inc-v-shell-oil-company-shell-pipe-line-corporation-amoco/

### Second check: not required


## KEHOE-086: Fed. R. Crim. P. 14

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 13 (slip op. at 13).

Authority type: court_rule; as written: under Rule 14; pincite: .

Cited for: District court may sever if prejudice

Quotes: []

Context: Bare rule reference; in context the criminal severance rule.

Fictional by design: False; 

### First check: VERIFIED

Read current text at Cornell LII; Rule 14(a) authorizes severance when joinder appears to prejudice a defendant or the government. Zafiro (read) quotes the earlier wording to the same effect ('if it appears that a defendant or the government is prejudiced by a joinder').

Excerpt read: (a) Relief. If the joinder of offenses or defendants ... appears to prejudice a defendant or the government, the court may order separate trials of counts, sever the defendants' trials, or provide any other relief that justice requires.

- https://www.law.cornell.edu/rules/frcrmp/rule_14

### Second check: not required


## KEHOE-087: Fed. R. Civ. P. 14 (as cited; Fed. R. Crim. P. 14 intended)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 13 (slip op. at 13).

Authority type: court_rule; as written: Fed. R. Civ. P. 14; pincite: .

Cited for: Severance of codefendants

Quotes: []

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

Kehoe cites 'Fed. R. Civ. P. 14' for severance of a criminal codefendant's trial. Read Fed. R. Civ. P. 14 at Cornell LII: it governs third-party practice in civil actions. The severance rule Kehoe describes is Fed. R. Crim. P. 14 (read), as Zafiro, cited in the same sentence, confirms. The error is in the court's own slip opinion and also appears in the reporter text on CourtListener ('Fed. R.Civ.P. 14').

Excerpt read: Fed. R. Civ. P. 14: 'Rule 14. Third-Party Practice'. Fed. R. Crim. P. 14(a): 'If the joinder of offenses or defendants ... appears to prejudice a defendant or the government, the court may ... sever the defendants' trials'.

- https://www.law.cornell.edu/rules/frcp/rule_14
- https://www.law.cornell.edu/rules/frcrmp/rule_14
- https://www.courtlistener.com/opinion/779816/united-states-v-chevie-obrien-kehoe-also-known-as-jonathan-collins-also/

### Second check: pending


## KEHOE-088: Zafiro v. United States, 506 U.S. 534 (1993)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: Zafiro v. United States, 506 U.S. 534, 535, 538-39 (1993); pincite: 535, 538-39.

Cited for: Severance discretionary under Rule 14

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; at 535 the Court introduces Rule 14 severance on prejudice, and at 538-39 it explains Rule 14 leaves tailoring of relief to the district court's discretion.

Excerpt read: Rule 14 of the Rules, in turn, permits a district court to grant a severance of defendants if "it appears that a defendant or the government is prejudiced by a joinder." ... Rule 14 does not require severance even [*539] if prejudice is shown; rather, it leaves the tailoring of the relief to be granted, if any, to the district court's sound discretion.

- https://www.courtlistener.com/opinion/112812/zafiro-v-united-states/

### Second check: not required


## KEHOE-089: United States v. Gravatt, 280 F.3d 1189 (8th Cir. 2002)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF pages 13-14 (slip op. at 13-14).

Authority type: case; as written: United States v. Gravatt, 280 F.3d 1189, 1991 (8th Cir. 2002); pincite: 1991 [sic].

Cited for: Reversal only on showing of real prejudice

Quotes: ['real prejudice, which is more than a showing [that] a separate trial would have improved the likelihood of acquittal.']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener text; the 'real prejudice' standard appears as quoted. Defect: the slip opinion's pin '1991' is garbled; the reporter version of Kehoe on CourtListener reads '280 F.3d 1189, 1191'.

Excerpt read: we will not reverse a district court's refusal to grant a severance absent a showing of "real prejudice," which is more than a showing a separate trial would have improved the likelihood of acquittal.

- https://www.courtlistener.com/opinion/776607/united-states-v-richard-c-gravatt/

### Second check: not required


## KEHOE-090: United States v. Frazier, 280 F.3d 835 (8th Cir. 2002)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 14 (slip op. at 14).

Authority type: case; as written: United States v. Frazier, 280 F.3d 835, 844 (8th Cir. 2002); pincite: 844.

Cited for: Rarely sever coconspirators

Quotes: ['[I]t will be the rare case, if ever, where a district court should sever the trial of alleged coconspirators.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; after the *844 marker the court states it will be the rare case, if ever, where coconspirators' trials should be severed, and that spillover concern was minimized by a limiting instruction.

Excerpt read: We have said many times that it will be the rare case, if ever, where a district court should sever the trial of alleged coconspirators. ... Any concern that the evidence implicating the other codefendants would spill over and prejudice Thomas was minimized by the district court's instruction

- https://www.courtlistener.com/opinion/3028394/united-states-v-phelix-frazier/

### Second check: not required


## KEHOE-091: United States v. Patterson, 140 F.3d 767 (8th Cir. 1998)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 14 (slip op. at 14).

Authority type: case; as written: citing United States v. Patterson, 140 F.3d 767, 774 (8th Cir. 1998); pincite: 774.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; after the *774 marker Patterson addresses severance of codefendants under Rule 14, reviewed for abuse of discretion requiring clear prejudice. Frazier cites Patterson at 774 for the severance standard.

Excerpt read: The district court may grant a severance where a defendant shows that he is prejudiced by a joint trial, however. See Fed.R.Crim.P. 14. On appeal the district court's decision is reviewed for abuse of discretion, which requires a showing of clear prejudice.

- https://www.courtlistener.com/opinion/3020623/united-states-v-gerald-lee-patterson/

### Second check: not required


## KEHOE-092: United States v. Frazier, 280 F.3d 835 (8th Cir. 2002)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 14 (slip op. at 14).

Authority type: case; as written: Frazier, 280 F.3d at 844; pincite: 844.

Cited for: Limiting instructions minimize spillover

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; after the *844 marker the court states it will be the rare case, if ever, where coconspirators' trials should be severed, and that spillover concern was minimized by a limiting instruction.

Excerpt read: We have said many times that it will be the rare case, if ever, where a district court should sever the trial of alleged coconspirators. ... Any concern that the evidence implicating the other codefendants would spill over and prejudice Thomas was minimized by the district court's instruction

- https://www.courtlistener.com/opinion/3028394/united-states-v-phelix-frazier/

### Second check: not required


## KEHOE-093: U.S. Const. amend. VI

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 14 (slip op. at 14).

Authority type: constitution; as written: Confrontation Clause of the Sixth Amendment; pincite: .

Cited for: Kehoe's confrontation argument

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Sixth Amendment text at Cornell LII; it guarantees confrontation and the assistance of counsel.

Excerpt read: to be confronted with the witnesses against him; ... and to have the Assistance of Counsel for his defence.

- https://www.law.cornell.edu/constitution/sixth_amendment

### Second check: not required


## KEHOE-094: Fed. R. Evid. 801(d)(2)(B)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 14 (slip op. at 14).

Authority type: court_rule; as written: Rule 801(d)(2)(B) of the Federal Rules of Evidence; pincite: .

Cited for: Adoptive admissions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Kehoe quotes the pre-2011 text. Read the current restyled rule at Cornell LII and the pre-2011 text as quoted in United States v. Williams, 87 F.3d 249 (8th Cir. 1996), on CourtListener; Kehoe's quotation matches the pre-2011 wording in effect when Kehoe was decided.

Excerpt read: Pre-2011 (as quoted in Williams): a statement is not hearsay if it is offered against a party and is "a statement of which the party has manifested an adoption or belief in its truth." Current: '(B) is one the party manifested that it adopted or believed to be true;'

- https://www.law.cornell.edu/rules/fre/rule_801
- https://www.courtlistener.com/opinion/720593/united-states-v-louis-williams/

### Second check: not required


## KEHOE-095: Maddox v. Patterson, 905 F.2d 1178 (8th Cir. 1990)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: Maddox v. Patterson, 905 F.2d 1178, 1179 (8th Cir. 1990); pincite: 1179.

Cited for: Evidentiary rulings reviewed for abuse of discretion

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; evidentiary rulings are reviewed for clear and prejudicial abuse of discretion (early in opinion, consistent with 1179).

Excerpt read: judge has wide discretion in ruling on the admissibility of evidence, and his decisions will not be disturbed unless there is a clear and prejudicial abuse of discretion.

- https://www.courtlistener.com/opinion/543169/notley-gwinn-maddox-jr-v-claude-patterson-jr/

### Second check: not required


## KEHOE-096: U.S. Const. amend. VI

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: constitution; as written: Confrontation Clause of the Sixth Amendment; pincite: .

Cited for: Violations reviewed for harmless error

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Sixth Amendment text at Cornell LII; it guarantees confrontation and the assistance of counsel.

Excerpt read: to be confronted with the witnesses against him; ... and to have the Assistance of Counsel for his defence.

- https://www.law.cornell.edu/constitution/sixth_amendment

### Second check: not required


## KEHOE-097: Chapman v. California, 386 U.S. 18 (1967)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: Chapman v. California, 386 U.S. 18, 22-23 (1967); pincite: 22-23.

Cited for: Harmless-error review of constitutional violations

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; federal constitutional errors may be harmless if harmless beyond a reasonable doubt (at 22-24).

Excerpt read: before a federal constitutional error can be held harmless, the court must be able to declare a belief that it was harmless beyond a reasonable doubt.

- https://www.courtlistener.com/opinion/107359/chapman-v-california/

### Second check: not required


## KEHOE-098: Lufkins v. Leapley, 965 F.2d 1477 (8th Cir. 1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: Lufkins v. Leapley, 965 F.2d 1477, 1480 (8th Cir. 1992); pincite: 1480.

Cited for: Confrontation violations subject to harmless error

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; before the *1481 marker the court holds Sixth Amendment confrontation violations are subject to harmless-error analysis, citing Chapman.

Excerpt read: Violations of the right to confront witnesses under the Sixth Amendment are subject to harmless error analysis.

- https://www.courtlistener.com/opinion/584171/dennis-lufkins-v-walter-leapley-warden-of-the-south-dakota-state/

### Second check: not required


## KEHOE-099: Fed. R. Evid. 801(d)(2)(B)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: court_rule; as written: Fed. R. Evid. 801(d)(2)(B); pincite: .

Cited for: Adoptive admission rule

Quotes: ['A statement is not hearsay if [it] is offered against a party and is a statement of which the party has manifested an adoption or belief in its truth.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Kehoe quotes the pre-2011 text. Read the current restyled rule at Cornell LII and the pre-2011 text as quoted in United States v. Williams, 87 F.3d 249 (8th Cir. 1996), on CourtListener; Kehoe's quotation matches the pre-2011 wording in effect when Kehoe was decided.

Excerpt read: Pre-2011 (as quoted in Williams): a statement is not hearsay if it is offered against a party and is "a statement of which the party has manifested an adoption or belief in its truth." Current: '(B) is one the party manifested that it adopted or believed to be true;'

- https://www.law.cornell.edu/rules/fre/rule_801
- https://www.courtlistener.com/opinion/720593/united-states-v-louis-williams/

### Second check: not required


## KEHOE-100: United States v. Disbrow, 768 F.2d 976 (8th Cir. 1985)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: United States v. Disbrow, 768 F.2d 976, 980-81 (8th Cir. 1985); pincite: 980-81.

Cited for: Requirements for adoptive admission

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the adoptive-admission requirements straddle the *981 marker (980-81).

Excerpt read: requires that the accusatory statement must be made in the defendant's presence, that [*981] the defendant must understand it, and that the defendant must have an opportunity to deny it.

- https://www.courtlistener.com/opinion/456007/united-states-v-jeffrey-keith-disbrow/

### Second check: not required


## KEHOE-101: United States v. Lilley, 581 F.2d 182 (8th Cir. 1978)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: citing United States v. Lilley, 581 F.2d 182, 187 (8th Cir. 1978); pincite: 187.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Lilley states the general rule for adoptive admissions (pin not separately checked).

Excerpt read: as a general rule, when an accusatory statement is made in the defendant's presence and hearing, and he understands it and has an opportunity to deny it, the statement and his failure to deny it are admissible against him.

- https://www.courtlistener.com/opinion/358620/united-states-v-camille-t-lilley/

### Second check: not required


## KEHOE-102: U.S. Const. amend. VI

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: constitution; as written: no Confrontation Clause problem; pincite: .

Cited for: Nonhearsay raises no confrontation issue

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Sixth Amendment text at Cornell LII; it guarantees confrontation and the assistance of counsel.

Excerpt read: to be confronted with the witnesses against him; ... and to have the Assistance of Counsel for his defence.

- https://www.law.cornell.edu/constitution/sixth_amendment

### Second check: not required


## KEHOE-103: United States v. Woods, 301 F.3d 556 (7th Cir. 2002)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: United States v. Woods, 301 F.3d 556, 561 (7th Cir. 2002); pincite: 561.

Cited for: Adopted statements raise no confrontation problem

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; before the *562 marker Woods holds that adopted statements are the defendant's own, so there is no hearsay and no confrontation problem.

Excerpt read: If the statements are Woods' own -- either by virtue of the fact he made or adopted them -- there is no hearsay and no confrontation problem because the witness against the defendant is himself.

- https://www.courtlistener.com/opinion/778894/united-states-v-charles-woods/

### Second check: not required


## KEHOE-104: Tennessee v. Street, 471 U.S. 409 (1985)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: see also Tennessee v. Street, 471 U.S. 409, 414 (1990); pincite: 414.

Cited for: Nonhearsay aspect raises no confrontation concerns

Quotes: ['The nonhearsay aspect of [the] confession . . . raises no confrontation clause concerns.']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener majority text; the quoted sentence appears at 414 (before the *415 marker). Defect: Kehoe dates the decision 1990; Street was decided in 1985.

Excerpt read: The nonhearsay aspect of Peele's confession -- not to prove what happened at the murder scene but to prove what happened when respondent confessed -- raises no Confrontation Clause concerns.

- https://www.courtlistener.com/opinion/111424/tennessee-v-street/

### Second check: not required


## KEHOE-105: Bruton v. United States, 391 U.S. 123 (1968)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: Bruton v. United States, 391 U.S. 123, 126 (1968); pincite: 126.

Cited for: Purpose of confrontation rule

Quotes: ['A major reason underlying the constitutional confrontation rule is to give a defendant charged with crime an opportunity to cross-examine the witnesses against him.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the quoted sentence appears verbatim (Bruton quoting Douglas/Pointer) early in the opinion, consistent with 126.

Excerpt read: "a major reason underlying the constitutional confrontation rule is to give a defendant charged with crime an opportunity to cross-examine the witnesses against him."

- https://www.courtlistener.com/opinion/107684/bruton-v-united-states/

### Second check: not required


## KEHOE-106: U.S. Const. amend. VI

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: constitution; as written: rights under the Confrontation Clause; pincite: .

Cited for: No violation

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Sixth Amendment text at Cornell LII; it guarantees confrontation and the assistance of counsel.

Excerpt read: to be confronted with the witnesses against him; ... and to have the Assistance of Counsel for his defence.

- https://www.law.cornell.edu/constitution/sixth_amendment

### Second check: not required


## KEHOE-107: United States v. Woods, 301 F.3d 556 (7th Cir. 2002)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: See Woods, 301 F.3d at 561; pincite: 561.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; before the *562 marker Woods holds that adopted statements are the defendant's own, so there is no hearsay and no confrontation problem.

Excerpt read: If the statements are Woods' own -- either by virtue of the fact he made or adopted them -- there is no hearsay and no confrontation problem because the witness against the defendant is himself.

- https://www.courtlistener.com/opinion/778894/united-states-v-charles-woods/

### Second check: not required


## KEHOE-108: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 15 (slip op. at 15).

Authority type: constitution; as written: Fifth Amendment privilege; pincite: .

Cited for: Lee's invocation

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## KEHOE-109: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 16 (slip op. at 16).

Authority type: constitution; as written: the Fifth Amendment privilege; pincite: .

Cited for: Defense witness immunity after invocation

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## KEHOE-110: United States v. Blanche, 149 F.3d 763 (8th Cir. 1998)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 16 (slip op. at 16).

Authority type: case; as written: United States v. Blanche, 149 F.3d 763, 767 (8th Cir. 1998); pincite: 767.

Cited for: Defense witness immunity is extraordinary remedy

Quotes: ["'extraordinary remedy' to be used sparingly and then only where the proffered evidence is 'clearly exculpatory.'"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Blanche (quoting Capozzi) states that defense-witness immunity, assuming authority exists, is an extraordinary remedy used only where the evidence is clearly exculpatory.

Excerpt read: "[e]ven assuming a district court has authority to immunize defense witnesses, ... it is clear that such an order is an extraordinary remedy, to be used sparingly, and then only where the proffered evidence is 'clearly exculpatory.'"

- https://www.courtlistener.com/opinion/755848/united-states-v-kawaskii-blanche/

### Second check: not required


## KEHOE-111: United States v. Young, 702 F.2d 133 (8th Cir. 1983)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 16 (slip op. at 16).

Authority type: case; as written: United States v. Young, 702 F.2d 133, 136 (8th Cir. 1983); pincite: 136.

Cited for: State procedural rules generally do not govern federal trial; apply here absent government objection

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Young holds a state-law rule (South Dakota's bar on Allen charges) does not govern procedure in federal court and applies Rule 30's objection requirement. Supports Kehoe's premise that state procedural rules generally do not govern a federal trial; Kehoe's further point (Arkansas rules govern here because the government did not object) is Kehoe's own application.

Excerpt read: While this may be the appropriate state law, this in no way governs procedure in the United States District Court. Rather, the federal rules of criminal procedure and federal decisions govern this criminal case.

- https://www.courtlistener.com/opinion/415448/united-states-v-irvin-edward-young-united-states-of-america-v-gilbert/

### Second check: not required


## KEHOE-112: Enterprise Leasing Co. v. Metropolitan Airports Commission, 250 F.3d 1215 (8th Cir. 2001)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 16 (slip op. at 16).

Authority type: case; as written: Enterprise Leasing Co. v. Metro. Airports Comm'n, 250 F.3d 1215, 1217 (8th Cir. 2001); pincite: 1217.

Cited for: De novo review of state-law questions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the court reviews de novo questions of state law decided by the district court.

Excerpt read: We review de novo questions of state law decided by the district court.

- https://www.courtlistener.com/opinion/773364/enterprise-leasing-company-doing-business-as-enterprise-rent-a-car-a/

### Second check: not required


## KEHOE-113: Ark. Code Ann. § 16-89-111(e)(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 16 (slip op. at 16).

Authority type: statute; as written: Ark. Code Ann. § 16-89-111(e)(1); pincite: .

Cited for: Accomplice testimony must be corroborated

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Arkansas Code text could not be fetched from Justia (HTTP 403). Read the statute as quoted in Munhall v. State, 337 Ark. 41, 986 S.W.2d 863 (1999), on CourtListener; it states the accomplice-corroboration rule Kehoe describes.

Excerpt read: A conviction cannot be had in any case of felony upon the testimony of an accomplice unless corroborated by other evidence tending to connect the defendant with the commission of the offense.

- https://www.courtlistener.com/opinion/2429039/munhall-v-state/

### Second check: not required


## KEHOE-114: Martin v. Norris, 82 F.3d 211 (8th Cir. 1996)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 16 (slip op. at 16).

Authority type: case; as written: Martin v. Norris, 82 F.3d 211, 214 (8th Cir. 1996); pincite: 214.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Martin describes Ark. Code § 16-89-111(e)(1) and quotes the corroboration test as Kehoe does.

Excerpt read: The corroborating evidence "must connect the accused with the crime and be independent of the evidence given by the accomplice.... The test ... is whether, if the accomplice's testimony were eliminated from the case, the other evidence independently establishes the crime and tends to connect the accused with its commission."

- https://www.courtlistener.com/opinion/716795/john-douglas-martin-v-larry-norris-director-arkansas-department-of/

### Second check: not required


## KEHOE-115: Marta v. State, 336 Ark. 67, 983 S.W.2d 924 (1999)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 16 (slip op. at 16).

Authority type: case; as written: Marta v. State, 983 S.W.2d 924, 927 (Ark. 1999); pincite: 927.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Marta states the 'totally eliminated' corroboration test and that corroborating evidence need not be so substantial in and of itself to sustain a conviction.

Excerpt read: The test for corroborating evidence is whether, if the testimony of the accomplice were totally eliminated from the case, the other evidence independently establishes the crime and tends to connect the accused with its commission. ... Corroborating evidence need not, however, be so substantial in and of itself to sustain a conviction.

- https://www.courtlistener.com/opinion/1678272/marta-v-state/

### Second check: not required


## KEHOE-116: Martin v. Norris, 82 F.3d 211 (8th Cir. 1996)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 16 (slip op. at 16).

Authority type: case; as written: Martin, 82 F.3d at 214; pincite: 214.

Cited for: Corroborating evidence must connect accused independently

Quotes: ["The corroborating evidence 'must connect the accused with the crime and be independent of the evidence given by the accomplice.'"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Martin describes Ark. Code § 16-89-111(e)(1) and quotes the corroboration test as Kehoe does.

Excerpt read: The corroborating evidence "must connect the accused with the crime and be independent of the evidence given by the accomplice.... The test ... is whether, if the accomplice's testimony were eliminated from the case, the other evidence independently establishes the crime and tends to connect the accused with its commission."

- https://www.courtlistener.com/opinion/716795/john-douglas-martin-v-larry-norris-director-arkansas-department-of/

### Second check: not required


## KEHOE-117: Marta v. State, 983 S.W.2d 924 (Ark. 1999)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 16 (slip op. at 16).

Authority type: case; as written: see Marta, 93 S.W.2d at 927; pincite: 927.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

The short form gives the volume as 93 S.W.2d; Marta v. State is reported at 983 S.W.2d 924 (full citation on the same page). 93 S.W.2d is a 1930s volume. Read Marta on CourtListener: the quoted corroboration test appears there, so the proposition is supported; the volume number is garbled in the court's slip opinion.

Excerpt read: The test for corroborating evidence is whether, if the testimony of the accomplice were totally eliminated from the case, the other evidence independently establishes the crime and tends to connect the accused with its commission. ... Corroborating evidence need not, however, be so substantial in and of itself to sustain a conviction.

- https://www.courtlistener.com/opinion/1678272/marta-v-state/

### Second check: pending


## KEHOE-118: Marta v. State, 983 S.W.2d 924 (Ark. 1999)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF pages 16-17 (slip op. at 16-17).

Authority type: case; as written: Marta, 93 S.W.2d at 927; pincite: 927.

Cited for: Test for sufficiency of corroboration

Quotes: ['if the testimony of the accomplice were totally eliminated from the case, the other evidence independently establishes the crime and tends to connect the accused with its commission. . . . Corroborating evidence need not, however, be so substantial in and of itself to sustain a conviction.']

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

The short form gives the volume as 93 S.W.2d; Marta v. State is reported at 983 S.W.2d 924 (full citation on the same page). 93 S.W.2d is a 1930s volume. Read Marta on CourtListener: the quoted corroboration test appears there, so the proposition is supported; the volume number is garbled in the court's slip opinion.

Excerpt read: The test for corroborating evidence is whether, if the testimony of the accomplice were totally eliminated from the case, the other evidence independently establishes the crime and tends to connect the accused with its commission. ... Corroborating evidence need not, however, be so substantial in and of itself to sustain a conviction.

- https://www.courtlistener.com/opinion/1678272/marta-v-state/

### Second check: pending


## KEHOE-119: Martin v. Norris, 82 F.3d 211 (8th Cir. 1996)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 17 (slip op. at 17).

Authority type: case; as written: Martin, 82 F.3d at 214; pincite: 214.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Martin describes Ark. Code § 16-89-111(e)(1) and quotes the corroboration test as Kehoe does.

Excerpt read: The corroborating evidence "must connect the accused with the crime and be independent of the evidence given by the accomplice.... The test ... is whether, if the accomplice's testimony were eliminated from the case, the other evidence independently establishes the crime and tends to connect the accused with its commission."

- https://www.courtlistener.com/opinion/716795/john-douglas-martin-v-larry-norris-director-arkansas-department-of/

### Second check: not required


## KEHOE-120: United States v. Enriquez, 201 F.3d 1072 (8th Cir. 2000)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 17 (slip op. at 17).

Authority type: case; as written: United States v. Enriquez, 201 F.3d 1072, 1074 (8th Cir. 2000); pincite: 1074.

Cited for: Credibility is for the jury

Quotes: ['[I]t is the sole province of the jury to weigh the credibility of a witness.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text (short opinion, 1072-75); the quoted sentence appears verbatim.

Excerpt read: We have stated numerous times that "it is the sole province of the jury to weigh the credibility of a witness."

- https://www.courtlistener.com/opinion/767424/united-states-v-rebecca-l-enriquez/

### Second check: not required


## KEHOE-121: United States v. Riley, 657 F.2d 1377 (8th Cir. 1981)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 18 (slip op. at 18).

Authority type: case; as written: United States v. Riley, 657 F.2d 1377, 1387 (8th Cir. 1981); pincite: 1387.

Cited for: Psychiatric examination ruling reviewed for abuse of discretion

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener majority text. Riley (quoting Russo) says 'Ordering a witness to undergo a psychological examination is a drastic measure'; Kehoe's quotation substitutes 'psychiatric' for 'psychological'. Proposition supported; pin not separately checked.

Excerpt read: "Ordering a witness to undergo a psychological examination is a drastic measure."

- https://www.courtlistener.com/opinion/393805/united-states-v-claude-leander-riley/

### Second check: not required


## KEHOE-122: United States v. Riley, 657 F.2d 1377 (8th Cir. 1981)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 18 (slip op. at 18).

Authority type: case; as written: Id. [Riley]; pincite: 1387.

Cited for: Ordering examination is drastic

Quotes: ['Ordering a witness to undergo a psychiatric examination is a drastic measure.']

Context: 

Fictional by design: False; 

### First check: VERIFIED_MINOR_DEFECT

Read CourtListener majority text. Riley (quoting Russo) says 'Ordering a witness to undergo a psychological examination is a drastic measure'; Kehoe's quotation substitutes 'psychiatric' for 'psychological'. Proposition supported; pin not separately checked.

Excerpt read: "Ordering a witness to undergo a psychological examination is a drastic measure."

- https://www.courtlistener.com/opinion/393805/united-states-v-claude-leander-riley/

### Second check: not required


## KEHOE-123: Barefoot v. Estelle, 463 U.S. 880 (1983)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 18 (slip op. at 18).

Authority type: case; as written: See Barefoot v. Estelle, 463 U.S. 880, 904 (1983); pincite: 904.

Cited for: Hypothetical-based psychiatric testimony admissible on future dangerousness

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; before the *905 marker the Court rejects the argument that future-dangerousness testimony may not be given in response to hypothetical questions.

Excerpt read: Expert testimony, whether in the form of an opinion based on hypothetical questions or otherwise, is commonly admitted as evidence where it might help the factfinder do its assigned job. ... we reject petitioner's constitutional arguments against the use of hypothetical questions.

- https://www.courtlistener.com/opinion/111017/barefoot-v-estelle/

### Second check: not required


## KEHOE-124: Kumho Tire Co. v. Carmichael, 526 U.S. 137 (1999)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 19 (slip op. at 19).

Authority type: case; as written: Kumho Tire Co. v. Carmichael, 526 U.S. 137, 147 (1999); pincite: 147.

Cited for: Expert testimony must be relevant and reliable

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; Kumho restates Daubert's requirement that expert testimony be relevant and reliable and that appellate courts review admission of expert testimony for abuse of discretion, with trial-court latitude. Individual pin pages (142, 147, 152) not separately checked against page markers.

Excerpt read: It pointed out that such testimony is admissible only if it is both relevant and reliable. ... a court of appeals is to apply an abuse-of-discretion standard when it "review[s] a trial court's decision to admit or exclude expert testimony."

- https://www.courtlistener.com/opinion/118271/kumho-tire-co-v-carmichael/

### Second check: not required


## KEHOE-125: Daubert v. Merrell Dow Pharmaceuticals, Inc., 509 U.S. 579 (1993)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 19 (slip op. at 19).

Authority type: case; as written: citing Daubert v. Merrell Dow Pharm., Inc., 509 U.S. 579, 589 (1993); pincite: 589.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the trial judge must ensure scientific testimony is not only relevant but reliable (at 589).

Excerpt read: the trial judge must ensure that any and all scientific testimony or evidence admitted is not only relevant, but reliable.

- https://www.courtlistener.com/opinion/112903/daubert-v-merrell-dow-pharmaceuticals-inc/

### Second check: not required


## KEHOE-126: United States v. Jolivet, 224 F.3d 902 (8th Cir. 2000)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 19 (slip op. at 19).

Authority type: case; as written: United States v. Jolivet, 224 F.3d 902, 905 (8th Cir. 2000); pincite: 905.

Cited for: Wide latitude on reliability

Quotes: ['The district court is afforded wide latitude in making its reliability and relevance determinations.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted 'wide latitude' sentence appears (citing Kumho at 152). Jolivet upheld expert handwriting testimony.

Excerpt read: The district court is afforded wide latitude in making its reliability and relevance determinations.

- https://www.courtlistener.com/opinion/770188/united-states-v-catherine-a-jolivet-also-known-as-catherine-a-vaho/

### Second check: not required


## KEHOE-127: Kumho Tire Co. v. Carmichael, 526 U.S. 137 (1999)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 19 (slip op. at 19).

Authority type: case; as written: citing Kumho Tire, 526 U.S. at 152; pincite: 152.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; Kumho restates Daubert's requirement that expert testimony be relevant and reliable and that appellate courts review admission of expert testimony for abuse of discretion, with trial-court latitude. Individual pin pages (142, 147, 152) not separately checked against page markers.

Excerpt read: It pointed out that such testimony is admissible only if it is both relevant and reliable. ... a court of appeals is to apply an abuse-of-discretion standard when it "review[s] a trial court's decision to admit or exclude expert testimony."

- https://www.courtlistener.com/opinion/118271/kumho-tire-co-v-carmichael/

### Second check: not required


## KEHOE-128: Kumho Tire Co. v. Carmichael, 526 U.S. 137 (1999)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 19 (slip op. at 19).

Authority type: case; as written: Kumho Tire, 526 U.S. at 142; pincite: 142.

Cited for: Abuse-of-discretion review of expert admission

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; Kumho restates Daubert's requirement that expert testimony be relevant and reliable and that appellate courts review admission of expert testimony for abuse of discretion, with trial-court latitude. Individual pin pages (142, 147, 152) not separately checked against page markers.

Excerpt read: It pointed out that such testimony is admissible only if it is both relevant and reliable. ... a court of appeals is to apply an abuse-of-discretion standard when it "review[s] a trial court's decision to admit or exclude expert testimony."

- https://www.courtlistener.com/opinion/118271/kumho-tire-co-v-carmichael/

### Second check: not required


## KEHOE-129: United States v. Jolivet, 224 F.3d 902 (8th Cir. 2000)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 19 (slip op. at 19).

Authority type: case; as written: Jolivet, 224 F.3d at 905; pincite: 905.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted 'wide latitude' sentence appears (citing Kumho at 152). Jolivet upheld expert handwriting testimony.

Excerpt read: The district court is afforded wide latitude in making its reliability and relevance determinations.

- https://www.courtlistener.com/opinion/770188/united-states-v-catherine-a-jolivet-also-known-as-catherine-a-vaho/

### Second check: not required


## KEHOE-130: Daubert v. Merrell Dow Pharmaceuticals, Inc., 509 U.S. 579 (1993)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 19 (slip op. at 19).

Authority type: case; as written: following a Daubert challenge; pincite: .

Cited for: Burden after Daubert challenge

Quotes: []

Context: Case name used as doctrine label.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the trial judge must ensure scientific testimony is not only relevant but reliable (at 589).

Excerpt read: the trial judge must ensure that any and all scientific testimony or evidence admitted is not only relevant, but reliable.

- https://www.courtlistener.com/opinion/112903/daubert-v-merrell-dow-pharmaceuticals-inc/

### Second check: not required


## KEHOE-131: United States v. Jolivet, 224 F.3d 902 (8th Cir. 2000)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 19 (slip op. at 19).

Authority type: case; as written: See Jolivet, 224 F.3d at 906; pincite: 906.

Cited for: Handwriting expert testimony properly admitted

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted 'wide latitude' sentence appears (citing Kumho at 152). Jolivet upheld expert handwriting testimony.

Excerpt read: The district court is afforded wide latitude in making its reliability and relevance determinations.

- https://www.courtlistener.com/opinion/770188/united-states-v-catherine-a-jolivet-also-known-as-catherine-a-vaho/

### Second check: not required


## KEHOE-132: United States v. Beckman, 222 F.3d 512 (8th Cir. 2000)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 19 (slip op. at 19).

Authority type: case; as written: United States v. Beckman, 222 F.3d 512, 520 (8th Cir. 2000); pincite: 520.

Cited for: Instructions reviewed for abuse of discretion

Quotes: ["We review the district court's jury instructions for abuse of discretion."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; both quoted passages appear (the second quoting Grain Land Coop). Kehoe's 'in the light of' adds 'the'.

Excerpt read: We review the district court's jury instructions for abuse of discretion. ... "whether the instructions, taken as a whole and viewed in light of the evidence and applicable law, 'fairly and adequately submitted the issues in the case to the jury.'"

- https://www.courtlistener.com/opinion/769887/united-states-v-bruce-a-beckman-united-states-of-america-v-thomas-kelly/

### Second check: not required


## KEHOE-133: United States v. Beckman, 222 F.3d 512 (8th Cir. 2000)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 19 (slip op. at 19).

Authority type: case; as written: Id. (internal quotes and citations omitted) [Beckman]; pincite: 520.

Cited for: Affirm if instructions fairly and adequately submitted issues

Quotes: ['the instructions, taken as a whole and viewed in the light of the evidence and applicable law, fairly and adequately submitted the issues in the case to the jury.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; both quoted passages appear (the second quoting Grain Land Coop). Kehoe's 'in the light of' adds 'the'.

Excerpt read: We review the district court's jury instructions for abuse of discretion. ... "whether the instructions, taken as a whole and viewed in light of the evidence and applicable law, 'fairly and adequately submitted the issues in the case to the jury.'"

- https://www.courtlistener.com/opinion/769887/united-states-v-bruce-a-beckman-united-states-of-america-v-thomas-kelly/

### Second check: not required


## KEHOE-134: United States v. McGinnis, 783 F.2d 755 (8th Cir. 1986)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 20 (slip op. at 20).

Authority type: case; as written: See United States v. McGinnis, 783 F.2d 755, 758 (8th Cir. 1986); pincite: 758.

Cited for: No need for cautionary instruction where accomplice testimony corroborated

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted sentence appears verbatim, citing Evans, 697 F.2d at 245.

Excerpt read: Decisions as to credibility and as to what weight particular testimony should receive properly rest with the jury.

- https://www.courtlistener.com/opinion/464858/united-states-v-marvin-wayne-mcginnis/

### Second check: not required


## KEHOE-135: United States v. McGinnis, 783 F.2d 755 (8th Cir. 1986)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 20 (slip op. at 20).

Authority type: case; as written: Id. [McGinnis]; pincite: 758.

Cited for: Credibility for the jury

Quotes: ['Decisions as to credibility and as to what weight particular testimony should receive properly rest with the jury.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted sentence appears verbatim, citing Evans, 697 F.2d at 245.

Excerpt read: Decisions as to credibility and as to what weight particular testimony should receive properly rest with the jury.

- https://www.courtlistener.com/opinion/464858/united-states-v-marvin-wayne-mcginnis/

### Second check: not required


## KEHOE-136: United States v. Evans, 697 F.2d 240 (8th Cir. 1983)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 20 (slip op. at 20).

Authority type: case; as written: citing United States v. Evans, 697 F.2d 240, 245 (8th Cir. 1983); pincite: 245.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Evans states that credibility and the weight of a witness's testimony rest with the jury.

Excerpt read: Credibility, i.e., the decision as to the appropriate weight to be accorded the testimony of a witness, rests with the jury.

- https://www.courtlistener.com/opinion/412743/united-states-v-joseph-evans/

### Second check: not required


## KEHOE-137: United States v. Holy Bear, 624 F.2d 853 (8th Cir. 1980)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 20 (slip op. at 20).

Authority type: case; as written: United States v. Holy Bear, 624 F.2d 853, 855 (8th Cir. 1980); pincite: 855.

Cited for: Unobjected instructions reviewed for plain error

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; failure to object to instructions bars review under Rule 30 unless the defect is plain error under Rule 52(b).

Excerpt read: failure to object to jury instructions usually bars appellate review, see Fed.R.Crim.P. 30, unless the alleged defect amounts to plain error under Fed.R.Crim.P. 52(b).

- https://www.courtlistener.com/opinion/379561/united-states-v-charles-curtis-holy-bear/

### Second check: not required


## KEHOE-138: Fed. R. Crim. P. 30

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 20 (slip op. at 20).

Authority type: court_rule; as written: Fed. R. Crim. P. 30; pincite: .

Cited for: Objection requirement

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; Rule 30(d) requires specific objection to instructions before deliberations; consistent with Kehoe's plain-error point (Holy Bear applies the same rule).

Excerpt read: (d) Objections to Instructions. A party who objects to any portion of the instructions or to a failure to give a requested instruction must inform the court of the specific objection and the grounds for the objection before the jury retires to deliberate.

- https://www.law.cornell.edu/rules/frcrmp/rule_30

### Second check: not required


## KEHOE-139: Fed. R. Crim. P. 52(b)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 20 (slip op. at 20).

Authority type: court_rule; as written: [Fed. R. Crim. P.] 52(b); pincite: .

Cited for: Plain error

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; plain error affecting substantial rights may be considered though not raised.

Excerpt read: (b) Plain Error. A plain error that affects substantial rights may be considered even though it was not brought to the court's attention.

- https://www.law.cornell.edu/rules/frcrmp/rule_52

### Second check: not required


## KEHOE-140: United States v. White, 241 F.3d 1015 (8th Cir. 2001)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF pages 20-21 (slip op. at 20-21).

Authority type: case; as written: United States v. White, 241 F.3d 1015, 1023 (8th Cir. 2001); pincite: 1023.

Cited for: Unpreserved prosecutorial-misconduct claim

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; White reviews unobjected prosecutorial comments only for plain error affecting substantial rights (pin not separately checked).

Excerpt read: While the prosecutor's comments are questionable, they do not rise to the level of plain error affecting White's substantial rights.

- https://www.courtlistener.com/opinion/772280/united-states-v-mark-white/

### Second check: not required


## KEHOE-141: Fed. R. Crim. P. 52(b)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 21 (slip op. at 21).

Authority type: court_rule; as written: Fed. R. Crim. P. 52(b); pincite: .

Cited for: Reverse only for plain error affecting substantial rights

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read text at Cornell LII; plain error affecting substantial rights may be considered though not raised.

Excerpt read: (b) Plain Error. A plain error that affects substantial rights may be considered even though it was not brought to the court's attention.

- https://www.law.cornell.edu/rules/frcrmp/rule_52

### Second check: not required


## KEHOE-142: United States v. Olano, 507 U.S. 725 (1993)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 21 (slip op. at 21).

Authority type: case; as written: United States v. Olano, 507 U.S. 725, 732 (1993); pincite: 732.

Cited for: Discretion to correct forfeited error

Quotes: ["Rule 52(b) leaves the decision to correct the forfeited error within the sound discretion of the court of appeals, and the court should not exercise that discretion unless the error 'seriously affect[s] the fairness, integrity or public reputation of judicial proceedings.'"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the quoted sentence appears verbatim (consistent with 732).

Excerpt read: Moreover, Rule 52(b) leaves the decision to correct the forfeited error within the sound discretion of the court of appeals, and the court should not exercise that discretion unless the error "'seriously affect[s] the fairness, integrity or public reputation of judicial proceedings.'"

- https://www.courtlistener.com/opinion/112848/united-states-v-olano/

### Second check: not required


## KEHOE-143: United States v. Jackson, 915 F.2d 359 (8th Cir. 1990)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Kehoe.pdf; location: PDF page 21 (slip op. at 21).

Authority type: case; as written: United States v. Jackson, 915 F.2d 359, 361 (8th Cir. 1990); pincite: 361.

Cited for: Vouching comments not plain error

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Jackson treats vouching for a witness as normally improper and reviews unobjected remarks for plain error.

Excerpt read: "Attempts to bolster a witness by vouching for his credibility are normally improper."

- https://www.courtlistener.com/opinion/548740/united-states-v-michaelis-billy-jackson/

### Second check: not required


## ELLISON-001: Iowa Code § 707.2 (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: Iowa Code § 707.2 (2020); pincite: .

Cited for: First-degree murder charge (class A felony)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; first-degree murder is a class A felony.

Excerpt read: 2. Murder in the first degree is a class "A" felony.

- https://www.legis.iowa.gov/docs/code/2020/707.2.pdf

### Second check: not required


## ELLISON-002: Iowa Code § 724.26(1) (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: id. § 724.26(1); pincite: .

Cited for: Felon in possession charge (class D felony)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; felon in possession is a class D felony.

Excerpt read: 1. A person who is convicted of a felony in a state or federal court ... and who knowingly has under the person's dominion and control or possession ... a firearm or offensive weapon is guilty of a class "D" felony.

- https://www.legis.iowa.gov/docs/code/2020/724.26.pdf

### Second check: not required


## ELLISON-003: Iowa Code § 707.4 (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: id. § 707.4; pincite: .

Cited for: Voluntary manslaughter (class C felony)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; voluntary manslaughter is a class C felony and an included offense of murder.

Excerpt read: 2. Voluntary manslaughter is a class "C" felony. 3. Voluntary manslaughter is an included offense under an indictment for murder in the first or second degree.

- https://www.legis.iowa.gov/docs/code/2020/707.4.pdf

### Second check: not required


## ELLISON-004: Iowa Code § 704.3

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 5 (slip op. at 5).

Authority type: statute; as written: Iowa Code § 704.3; pincite: .

Cited for: Justified use of reasonable force

Quotes: ['the person reasonably believes that such force is necessary to defend o neself or another from any actual or imminent use of unlawful force.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; matches Ellison's quotation and the reasonable-belief element cited in the rubric.

Excerpt read: 704.3 Defense of self or another. A person is justified in the use of reasonable force when the person reasonably believes that such force is necessary to defend oneself or another from any actual or imminent use of unlawful force.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-005: Iowa Code § 704.1(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 6 (slip op. at 6).

Authority type: statute; as written: Id. § 704.1(1); pincite: .

Cited for: Definition of reasonable force

Quotes: ['that force and no more which a reasonable person, in like circumstances, would judge to be necessary to prevent an injury or loss.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; Ellison's quotations of the reasonable-force and deadly-force language match subsection 1.

Excerpt read: 1. "Reasonable force" means that force and no more which a reasonable person, in like circumstances, would judge to be necessary to prevent an injury or loss and can include deadly force if it is reasonable to believe that such force is necessary to avoid injury or risk to one's life or safety or the life or safety of another

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-006: Iowa Code § 704.1(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 6 (slip op. at 6).

Authority type: statute; as written: Id. [§ 704.1(1)]; pincite: .

Cited for: Deadly force reasonable if necessary to avoid injury or risk to life

Quotes: ["is necessary to avoid injury or risk to one's life or safety or the life or safety of another."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; Ellison's quotations of the reasonable-force and deadly-force language match subsection 1.

Excerpt read: 1. "Reasonable force" means that force and no more which a reasonable person, in like circumstances, would judge to be necessary to prevent an injury or loss and can include deadly force if it is reasonable to believe that such force is necessary to avoid injury or risk to one's life or safety or the life or safety of another

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-007: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 6 (slip op. at 6).

Authority type: case; as written: See, e.g., State v. Lorenzo Baltazar, 935 N.W.2d 862, 870 (Iowa 2019); pincite: 870.

Cited for: Force generally not justified when person can avoid it by retreating or alternate course

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## ELLISON-008: 2017 Iowa Acts ch. 69, § 37 (codified at Iowa Code § 704.1(3) (2018))

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 6 (slip op. at 6).

Authority type: statute; as written: 2017 Iowa Acts ch. 69, § 37; pincite: .

Cited for: 2017 stand-your-ground amendment

Quotes: ['[a] person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

The session law itself was not opened; the official 2020 Code history note for § 704.1 credits '2017 Acts, ch 69, §37', and Lorenzo Baltazar (read) describes the 2017 amendment adding subsection 3. Supports Ellison's citation.

Excerpt read: [C79, 81, §704.1; 81 Acts, ch 204, §2] 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-009: Iowa Code § 704.1(3)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 6 (slip op. at 6).

Authority type: statute; as written: (codified at Iowa Code § 704.1(3) (2018)); pincite: .

Cited for: Codification of the 2017 amendment

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (unchanged since 2017 Iowa Acts ch. 69, § 37, per the history note). By negative implication a person engaged in illegal activity has a duty to retreat, as Ellison (at 8) and Lorenzo Baltazar hold; the subsection itself states only the no-duty rule for persons not engaged in illegal activity.

Excerpt read: 3. A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force as specified in this chapter. ... 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-010: State v. Williams, 929 N.W.2d 621 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 6 (slip op. at 6).

Authority type: case; as written: State v. Williams, 929 N.W.2d 621, 637 (Iowa 2019); pincite: 637.

Cited for: No duty to retreat for persons lawfully present and not engaged in illegal activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Williams quotes § 704.1(3) (2018) and describes it as a new stand-your-ground provision eliminating any duty to retreat if one is not engaged in illegal activity. Pin 637 not separately checked.

Excerpt read: Most notable is subsection 3, a new stand your ground provision, which eliminates any duty to retreat before using force if one is not engaged in illegal activity.

- https://www.courtlistener.com/opinion/4623040/state-of-iowa-v-antoine-tyree-williams/

### Second check: not required


## ELLISON-011: Iowa Code § 704.1(3)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 7 (slip op. at 7).

Authority type: statute; as written: section 704.1(3); pincite: .

Cited for: Instruction 29 restates § 704.1(3) in negative form

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (unchanged since 2017 Iowa Acts ch. 69, § 37, per the history note). By negative implication a person engaged in illegal activity has a duty to retreat, as Ellison (at 8) and Lorenzo Baltazar hold; the subsection itself states only the no-duty rule for persons not engaged in illegal activity.

Excerpt read: 3. A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force as specified in this chapter. ... 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-012: Iowa Code § 704.1(3)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 7 (slip op. at 7).

Authority type: statute; as written: See Iowa Code § 704.1(3); pincite: .

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (unchanged since 2017 Iowa Acts ch. 69, § 37, per the history note). By negative implication a person engaged in illegal activity has a duty to retreat, as Ellison (at 8) and Lorenzo Baltazar hold; the subsection itself states only the no-duty rule for persons not engaged in illegal activity.

Excerpt read: 3. A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force as specified in this chapter. ... 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-013: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: In State v. Lorenzo Baltazar ... 935 N.W.2d at 870; pincite: 870.

Cited for: After 2017 amendment no duty to retreat for person lawfully present and not engaged in illegal activity

Quotes: []

Context: This page is the 'slip op. at 8' cited in assignment 1 criteria 7 and 9.

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## ELLISON-014: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: Id. [Lorenzo Baltazar, 935 N.W.2d at 870]; pincite: 870.

Cited for: Duty to retreat continues for person engaged in illegal activity

Quotes: ['[T]he 2017 amendment changed—but did not eliminate—the implied duty to follow an alternative course of action.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## ELLISON-015: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: Id. [Lorenzo Baltazar]; pincite: 870.

Cited for: Usual duty to retreat still exists if engaged in illegal activity

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## ELLISON-016: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: Id. at 871; pincite: 871.

Cited for: Baltazar claimed ineffective assistance for not requesting stand-your-ground instruction

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## ELLISON-017: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: Id. [Lorenzo Baltazar, at 871]; pincite: 871.

Cited for: Defendant engaged in illegal activity not entitled to stand-your-ground instruction

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## ELLISON-018: State v. Schuler, 774 N.W.2d 294 (Iowa 2009)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: State v. Schuler, 774 N.W.2d 294, 297 (Iowa 2009); pincite: 297.

Cited for: First determine whether instructions correctly state the law

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Schuler reviews whether an instruction is a correct statement of the law (the proposition for which Ellison cites it). Pin not separately checked.

Excerpt read: Although an instruction need not contain or mirror the precise language of the applicable statute, it must be a correct statement of the law.

- https://www.courtlistener.com/opinion/1666722/state-v-schuler/

### Second check: not required


## ELLISON-019: Iowa Code § 704.1(3)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 8 (slip op. at 8).

Authority type: statute; as written: Iowa Code section 704.1(3); pincite: .

Cited for: Instruction 29 restates the statute

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (unchanged since 2017 Iowa Acts ch. 69, § 37, per the history note). By negative implication a person engaged in illegal activity has a duty to retreat, as Ellison (at 8) and Lorenzo Baltazar hold; the subsection itself states only the no-duty rule for persons not engaged in illegal activity.

Excerpt read: 3. A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force as specified in this chapter. ... 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-020: State v. Liggins, 557 N.W.2d 263 (Iowa 1996)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: State v. Liggins, 557 N.W.2d 263, 267 (Iowa 1996); pincite: 267.

Cited for: Instructions must be supported by substantial evidence

Quotes: ['supported by substantial evidence.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Liggins reviews instructions to decide whether they are correct statements of law and supported by substantial evidence, matching the quoted phrase.

Excerpt read: We review jury instructions to decide if they are correct statements of the law and are supported by substantial evidence.

- https://www.courtlistener.com/opinion/2226571/state-v-liggins/

### Second check: not required


## ELLISON-021: Vachon v. Broadlawns Medical Foundation, 490 N.W.2d 820 (Iowa 1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: Vachon v. Broadlawns Med. Found., 490 N.W.2d 820, 822 (Iowa 1992); pincite: 822.

Cited for: Unrelated instructions should not be submitted

Quotes: ['Requested instructions that are not related to the factual issues to be decided by the jury should not be submitted even though they may set out a correct statement of the law.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted sentence appears verbatim.

Excerpt read: Requested instructions that are not related to the factual issues to be decided by the jury should not be submitted even though they may set out a correct statement of the law.

- https://www.courtlistener.com/opinion/2116971/vachon-v-broadlawns-medical-foundation/

### Second check: not required


## ELLISON-022: State v. Shanahan, 712 N.W.2d 121 (Iowa 2006)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: State v. Shanahan, 712 N.W.2d 121, 134 (Iowa 2006); pincite: 134.

Cited for: State bears burden to disprove justification beyond a reasonable doubt

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers; between *134 and *135 the court states that because the defendant raised justification, the State was required to prove she acted without justification.

Excerpt read: Because Dixie raised justification as a defense, the State was required to prove she acted without justification.

- https://www.courtlistener.com/opinion/1789697/state-v-shanahan/

### Second check: not required


## ELLISON-023: State v. Marin, 788 N.W.2d 833 (Iowa 2010)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: State v. Marin, 788 N.W.2d 833, 838 (Iowa 2010); pincite: 838.

Cited for: No particular form of instruction required

Quotes: ['to give any particular form of an instruction; rather, the court must merely give instructions that fairly state the law as applied to the facts of the case.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted sentence appears verbatim. Alcala (read) lists Marin among cases it overruled on the standard of review for refusing requested instructions, consistent with 'overruled on other grounds'.

Excerpt read: In doing so, the court is not required to give any particular form of an instruction; rather, the court must merely give instructions that fairly state the law as applied to the facts of the case.

- https://www.courtlistener.com/opinion/1889875/state-v-marin/

### Second check: not required


## ELLISON-024: Alcala v. Marriott International, Inc., 880 N.W.2d 699 (Iowa 2016)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: overruled on other grounds by Alcala v. Marriott Int'l, Inc., 880 N.W.2d 699 (Iowa 2016); pincite: .

Cited for: Subsequent history of Marin

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Alcala overrules prior cases, including State v. Marin, 788 N.W.2d at 836, to the extent they applied abuse-of-discretion review to nondiscretionary refusals of requested instructions -- an issue other than the one for which Ellison cites Marin.

Excerpt read: ... State v. Marin, 788 N.W.2d 833, 836 (Iowa 2010) ... extend the abuse-of-discretion analysis to nondiscretionary refusals to give requested jury instructions supported by the evidence and applicable law, we overrule them on that issue.

- https://www.courtlistener.com/opinion/3212053/brenda-j-alcala-v-marriott-international-inc-and-courtyard-management/

### Second check: not required


## ELLISON-025: Iowa Code § 704.1(3)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 10, footnote 1 (slip op. at 10 n.1).

Authority type: statute; as written: Iowa Code section 704.1(3); pincite: .

Cited for: Illegal activity does not alone leave a person defenseless

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (unchanged since 2017 Iowa Acts ch. 69, § 37, per the history note). By negative implication a person engaged in illegal activity has a duty to retreat, as Ellison (at 8) and Lorenzo Baltazar hold; the subsection itself states only the no-duty rule for persons not engaged in illegal activity.

Excerpt read: 3. A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force as specified in this chapter. ... 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-026: Iowa Code § 704.6

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 10, footnote 1 (slip op. at 10 n.1).

Authority type: statute; as written: section 704.6; pincite: .

Cited for: Limited circumstances with no justification defense

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; lists when justification is unavailable (forcible felony, riot, duel; provocation with intent; provocation by unlawful acts subject to exceptions), as Ellison n.1 describes.

Excerpt read: 704.6 When defense not available. The defense of justification is not available to the following: 1. One who is participating in a forcible felony, or riot, or a duel. 2. One who initially provokes the use of force against oneself, with the intent to use such force as an excuse to inflict injury on the assailant. 3. One who initially provokes the use of force against oneself by one's unlawful acts, unless: ...

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-027: Iowa Code § 704.6

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 10, footnote 1 (slip op. at 10 n.1).

Authority type: statute; as written: See Iowa Code § 704.6; pincite: .

Cited for: Forcible felony, riot, provocation exceptions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; lists when justification is unavailable (forcible felony, riot, duel; provocation with intent; provocation by unlawful acts subject to exceptions), as Ellison n.1 describes.

Excerpt read: 704.6 When defense not available. The defense of justification is not available to the following: 1. One who is participating in a forcible felony, or riot, or a duel. 2. One who initially provokes the use of force against oneself, with the intent to use such force as an excuse to inflict injury on the assailant. 3. One who initially provokes the use of force against oneself by one's unlawful acts, unless: ...

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-028: Iowa Code § 704.1(3)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 10, footnote 1 (slip op. at 10 n.1).

Authority type: statute; as written: Section 704.1(3); pincite: .

Cited for: Persons engaged in illegal activity may not stand their ground if retreat possible

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (unchanged since 2017 Iowa Acts ch. 69, § 37, per the history note). By negative implication a person engaged in illegal activity has a duty to retreat, as Ellison (at 8) and Lorenzo Baltazar hold; the subsection itself states only the no-duty rule for persons not engaged in illegal activity.

Excerpt read: 3. A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force as specified in this chapter. ... 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-029: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 10, footnote 1 (slip op. at 10 n.1).

Authority type: case; as written: See Lorenzo Baltazar, 935 N.W.2d at 870; pincite: 870.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## ELLISON-030: Model Penal Code § 3.04 (Am. L. Inst. 1985)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 11 (slip op. at 11).

Authority type: other; as written: See, e.g., Model Penal Code § 3.04 (Am. L. Inst. 1985); pincite: .

Cited for: Duty to retreat as exception to justification

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

The ALI text is not freely available; read § 3.04(2)(b)(ii) and the 1985 commentaries as quoted in State v. Anderson (Conn. Aug. 31, 1993), on CourtListener. The quoted text shows the MPC treats the retreat rule as a limitation within the self-defense justification, consistent with Ellison's 'See, e.g.' use. Evidence is a judicial quotation, not the ALI publication itself.

Excerpt read: The Model Penal Code § 3.04 (2) (b) (ii) states that the use of deadly force in self-defense is not justifiable if "the actor knows that he can avoid the necessity of using such force with complete safety by retreating . . . ."

- https://www.courtlistener.com/opinion/7895478/state-v-anderson/

### Second check: not required


## ELLISON-031: Iowa Code § 704.1(3)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 11 (slip op. at 11).

Authority type: statute; as written: the section 704.1(3); pincite: .

Cited for: Source of 'illegal activity' term

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (unchanged since 2017 Iowa Acts ch. 69, § 37, per the history note). By negative implication a person engaged in illegal activity has a duty to retreat, as Ellison (at 8) and Lorenzo Baltazar hold; the subsection itself states only the no-duty rule for persons not engaged in illegal activity.

Excerpt read: 3. A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force as specified in this chapter. ... 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-032: Iowa Code § 704.1(3)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 11 (slip op. at 11).

Authority type: statute; as written: Iowa Code § 704.1(3); pincite: .

Cited for: Same

Quotes: ['A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (unchanged since 2017 Iowa Acts ch. 69, § 37, per the history note). By negative implication a person engaged in illegal activity has a duty to retreat, as Ellison (at 8) and Lorenzo Baltazar hold; the subsection itself states only the no-duty rule for persons not engaged in illegal activity.

Excerpt read: 3. A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force as specified in this chapter. ... 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-033: U.S. Const. amend. XIV

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 11 (slip op. at 11).

Authority type: constitution; as written: the Fourteenth Amendment to the United States Constitution; pincite: .

Cited for: Due process guarantee

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fourteenth Amendment text at Cornell LII; § 1 contains the Due Process Clause through which Malloy incorporates the self-incrimination privilege.

Excerpt read: nor shall any State deprive any person of life, liberty, or property, without due process of law

- https://www.law.cornell.edu/constitution/amendmentxiv

### Second check: not required


## ELLISON-034: Iowa Const. art. I, § 9

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 11 (slip op. at 11).

Authority type: constitution; as written: article I, section 9 of the Iowa Constitution; pincite: .

Cited for: Due process guarantee

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the codified Iowa Constitution published by the Iowa Legislature; article I, section 9 contains the due process clause.

Excerpt read: SEC. 9. The right of trial by jury shall remain inviolate; ... but no person shall be deprived of life, liberty, or property, without due process of law.

- https://www.legis.iowa.gov/docs/publications/icnst/402726.pdf

### Second check: not required


## ELLISON-035: State v. Newton, 929 N.W.2d 250 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: State v. Newton, 929 N.W.2d 250, 255 (Iowa 2019); pincite: 255.

Cited for: Due process guarantees

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; before the *256 marker Newton explains that the federal and Iowa due process clauses (U.S. Const. amend. XIV, § 1; Iowa Const. art. I, § 9) forbid vague criminal statutes.

Excerpt read: must comply with the fundamental concepts of fairness implicit in the constitutional right to "due process of law." U.S. Const. amend. XIV, § 1; Iowa Const. art. I, § 9 ... The Due Process Clauses of the United States and Iowa Constitutions prohibit vague statutes.

- https://www.courtlistener.com/opinion/4627215/state-of-iowa-v-timothy-alvin-newton/

### Second check: not required


## ELLISON-036: Johnson v. United States, 576 U.S. 591 (2015)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: Johnson v. United States, 576 U.S. 591, 595 (2015); pincite: 595.

Cited for: Void-for-vagueness standard

Quotes: ['a criminal law so vague that it fails to give ordinary people fair notice of the conduct it punishes, or so standardless that it invites arbitrary enforcement.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the quoted vagueness formulation appears verbatim (at 595).

Excerpt read: ... under a criminal law so vague that it fails to give ordinary people fair notice of the conduct it punishes, or so standardless that it invites arbitrary enforcement.

- https://www.courtlistener.com/opinion/2812210/johnson-v-united-states/

### Second check: not required


## ELLISON-037: Nguyen v. State, 878 N.W.2d 744 (Iowa 2016)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: See, e.g., Nguyen v. State, 878 N.W.2d 744, 755 (Iowa 2016); pincite: 755.

Cited for: Apply federal standard where no different state construction argued

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Nguyen reserves the right to interpret the Iowa Constitution differently even where parties advance no different standard, and applies the federal framework where no distinction is argued; it also restates the Strickland two-prong test (the proposition for which Kuhse cites it at 752). Pins not separately checked.

Excerpt read: "Even in these cases in which no substantive distinction had been made between state and federal constitutional provisions, we reserve the right to apply the principles differently under the state constitution compared to its federal counterpart."

- https://www.courtlistener.com/opinion/3184687/phuoc-nguyen-v-state-of-iowa/

### Second check: not required


## ELLISON-038: Bonilla v. Iowa Board of Parole, 930 N.W.2d 751 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: See Bonilla v. Iowa Bd. of Parole, 930 N.W.2d 751, 764 (Iowa 2019); pincite: 764.

Cited for: As-applied challenge

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; before the *765 marker Bonilla defines an as-applied challenge as alleging the statute is unconstitutional as applied to a particular set of facts.

Excerpt read: By contrast, "an as-applied challenge alleges the statute is unconstitutional as applied to a particular set of facts."

- https://www.courtlistener.com/opinion/4635124/julio-bonilla-v-iowa-board-of-parole/

### Second check: not required


## ELLISON-039: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: Lorenzo Baltazar, 936 N.W.2d 862; pincite: .

Cited for: Defendant in Lorenzo Baltazar argued illegal activity must be germane

Quotes: []

Context: 

Fictional by design: False; 

### First check: WRONG_CITATION_REAL_CASE

Volume given as 936 N.W.2d; the same opinion cites the case as 935 N.W.2d 862 four times (and Kuhse also uses 935 N.W.2d 862). The case and proposition are real (Lorenzo Baltazar slip opinion read; it addresses the germaneness argument), but the volume is garbled in the court's slip opinion.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: pending


## ELLISON-040: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: Id. at 871; pincite: 871.

Cited for: Baltazar's germaneness argument

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## ELLISON-041: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: Id. [Lorenzo Baltazar]; pincite: 871.

Cited for: Baltazar argued handgun possession irrelevant to duty to retreat

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## ELLISON-042: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: Id. [Lorenzo Baltazar]; pincite: 871.

Cited for: Handgun possession directly related to shooting death

Quotes: ["[e]ven assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the s hooting death."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## ELLISON-043: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: Id. [Lorenzo Baltazar]; pincite: 871.

Cited for: Illegal activity disqualified Baltazar from stand-your-ground exception

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## ELLISON-044: Iowa Code § 704.1(3)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 13 (slip op. at 13).

Authority type: statute; as written: section 704.1(3); pincite: .

Cited for: Illegal activity under the statute

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (unchanged since 2017 Iowa Acts ch. 69, § 37, per the history note). By negative implication a person engaged in illegal activity has a duty to retreat, as Ellison (at 8) and Lorenzo Baltazar hold; the subsection itself states only the no-duty rule for persons not engaged in illegal activity.

Excerpt read: 3. A person who is not engaged in illegal activity has no duty to retreat from any place where the person is lawfully present before using force as specified in this chapter. ... 2017 Acts, ch 69, §37

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-045: Iowa Code § 708.8

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 13 (slip op. at 13).

Authority type: statute; as written: See Iowa Code § 708.8; pincite: .

Cited for: Elements of going armed with intent

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; going armed with intent.

Excerpt read: A person who goes armed with any dangerous weapon with the intent to use without justification such weapon against the person of another commits a class "D" felony.

- https://www.legis.iowa.gov/docs/code/2020/708.8.pdf

### Second check: not required


## ELLISON-046: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: State v. Harris, 891 N.W.2d 182, 186 (Iowa 2017); pincite: 186.

Cited for: Going armed requires movement

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## ELLISON-047: State v. Pearson, 804 N.W.2d 260 (Iowa 2011)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: State v. Pearson, 804 N.W.2d 260, 265 n.1 (Iowa 2011); pincite: 265 n.1.

Cited for: Same (collecting cases)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Pearson reversed a going-armed conviction because the uniform marshaling instruction omitted the movement element, and its footnote addresses the element (Ellison cites 265 n.1, 'collecting cases'). Pin not separately checked.

Excerpt read: We reverse the district court's conviction of Pearson for going armed and remand for a new trial on that charge using a corrected marshaling instruction that includes the element of "movement."

- https://www.courtlistener.com/opinion/4472400/state-of-iowa-v-jesse-john-pearson/

### Second check: not required


## ELLISON-048: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 14 (slip op. at 14).

Authority type: constitution; as written: The Fifth Amendment to the United States Constitution; pincite: .

Cited for: Privilege against self-incrimination

Quotes: ['[n]o person . . . shall be compelled in any criminal case to be a witness against himself.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## ELLISON-049: U.S. Const. amend. XIV

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 14 (slip op. at 14).

Authority type: constitution; as written: the Fourteenth Amendment; pincite: .

Cited for: Incorporation against the states

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fourteenth Amendment text at Cornell LII; § 1 contains the Due Process Clause through which Malloy incorporates the self-incrimination privilege.

Excerpt read: nor shall any State deprive any person of life, liberty, or property, without due process of law

- https://www.law.cornell.edu/constitution/amendmentxiv

### Second check: not required


## ELLISON-050: Malloy v. Hogan, 378 U.S. 1 (1964)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 14 (slip op. at 14).

Authority type: case; as written: See Malloy v. Hogan, 378 U.S. 1, 2–6 (1964); pincite: 2-6.

Cited for: Self-incrimination privilege applies to states

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the Fourteenth Amendment secures against state invasion the same privilege the Fifth Amendment guarantees.

Excerpt read: The Fourteenth Amendment secures against state invasion the same privilege that the Fifth Amendment guarantees against federal infringement

- https://www.courtlistener.com/opinion/106862/malloy-v-hogan/

### Second check: not required


## ELLISON-051: State v. Gibbs, 941 N.W.2d 888 (Iowa 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 14 (slip op. at 14).

Authority type: case; as written: See State v. Gibbs, 941 N.W.2d 888, 894 (Iowa 2020); pincite: 894.

Cited for: Iowa Constitution lacks language tracking the Fifth Amendment

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-1298, Apr. 17, 2020). The majority states that the right against compulsory self-incrimination is protected by the Iowa due process clause (art. I, § 9), holds that an instruction authorizing an inference of guilt from breach of the § 704.2B(1) reporting duty penalized silence, refers to failure to 'affirmatively seek out the authorities and speak to them prearrest', expressly does not address § 704.2B(2), and says the jury holds it against the defendant 'in some significant but indeterminate way'. All quotations Ellison attributes to Gibbs appear. The slip has no N.W.2d page markers, so pins 894-900 could not be checked.

Excerpt read: A jury instruction authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities exacts a significant penalty on the defendant's right to remain silent. ... failing to affirmatively seek out the authorities and speak to them prearrest--with no Fifth Amendment exception. ... We do not address the constitutional ramifications of a jury instruction based only on section 704.2B(2).

- https://www.courtlistener.com/opinion/4746140/state-of-iowa-v-levi-gibbs-iii/

### Second check: not required


## ELLISON-052: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 14 (slip op. at 14).

Authority type: constitution; as written: the Fifth Amendment's language; pincite: .

Cited for: Comparison with Iowa Constitution

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## ELLISON-053: State v. Gibbs, 941 N.W.2d 888 (Iowa 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 14 (slip op. at 14).

Authority type: case; as written: Id. [Gibbs]; pincite: 894.

Cited for: Article I, section 9 due process provides self-incrimination protection

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-1298, Apr. 17, 2020). The majority states that the right against compulsory self-incrimination is protected by the Iowa due process clause (art. I, § 9), holds that an instruction authorizing an inference of guilt from breach of the § 704.2B(1) reporting duty penalized silence, refers to failure to 'affirmatively seek out the authorities and speak to them prearrest', expressly does not address § 704.2B(2), and says the jury holds it against the defendant 'in some significant but indeterminate way'. All quotations Ellison attributes to Gibbs appear. The slip has no N.W.2d page markers, so pins 894-900 could not be checked.

Excerpt read: A jury instruction authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities exacts a significant penalty on the defendant's right to remain silent. ... failing to affirmatively seek out the authorities and speak to them prearrest--with no Fifth Amendment exception. ... We do not address the constitutional ramifications of a jury instruction based only on section 704.2B(2).

- https://www.courtlistener.com/opinion/4746140/state-of-iowa-v-levi-gibbs-iii/

### Second check: not required


## ELLISON-054: Iowa Const. art. I, § 9

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 14 (slip op. at 14).

Authority type: constitution; as written: article I, section 9 of the Iowa Constitution; pincite: .

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the codified Iowa Constitution published by the Iowa Legislature; article I, section 9 contains the due process clause.

Excerpt read: SEC. 9. The right of trial by jury shall remain inviolate; ... but no person shall be deprived of life, liberty, or property, without due process of law.

- https://www.legis.iowa.gov/docs/publications/icnst/402726.pdf

### Second check: not required


## ELLISON-055: State v. Iowa District Court, 801 N.W.2d 513 (Iowa 2011)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 14 (slip op. at 14).

Authority type: case; as written: State v. Iowa Dist. Ct., 801 N.W.2d 513, 518 n.2 (Iowa 2011); pincite: 518 n.2.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; footnote 2 states the Iowa Constitution has no express self-incrimination provision but the right is implicit in article I, section 9 due process (cited at 518 n.2).

Excerpt read: Although the Iowa Constitution does not contain an equivalent provision against self-incrimination, we have held such a right to be implicit in the "due process of law" guaranteed by Article I, section 9.

- https://www.courtlistener.com/opinion/8280238/state-v-iowa-district-court-for-webster-county/

### Second check: not required


## ELLISON-056: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 15 (slip op. at 15).

Authority type: constitution; as written: under the Fifth Amendment; pincite: .

Cited for: Analysis framework

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## ELLISON-057: Nguyen v. State, 878 N.W.2d 744 (Iowa 2016)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: See, e.g., Nguyen, 878 N.W.2d at 755; pincite: 755.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Nguyen reserves the right to interpret the Iowa Constitution differently even where parties advance no different standard, and applies the federal framework where no distinction is argued; it also restates the Strickland two-prong test (the proposition for which Kuhse cites it at 752). Pins not separately checked.

Excerpt read: "Even in these cases in which no substantive distinction had been made between state and federal constitutional provisions, we reserve the right to apply the principles differently under the state constitution compared to its federal counterpart."

- https://www.courtlistener.com/opinion/3184687/phuoc-nguyen-v-state-of-iowa/

### Second check: not required


## ELLISON-058: Iowa Code § 704.2B(2)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 15 (slip op. at 15).

Authority type: statute; as written: section 704.2B(2); pincite: .

Cited for: Instruction 32 echoed statute

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; matches Ellison's block quotation of subsection 2.

Excerpt read: 2. The person using deadly force shall not intentionally destroy, alter, conceal, or disguise physical evidence relating to the person's use of deadly force, and the person shall not intentionally intimidate witnesses

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-059: Iowa Code § 704.2B(2)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 15 (slip op. at 15).

Authority type: statute; as written: Iowa Code § 704.2B(2); pincite: .

Cited for: Statutory text

Quotes: ["The person using deadly force shall not intentionally destroy, alter, conceal, or disguise physical evidence relating to the person's use of deadly force, and the person shall not intentionally intimidate witnesses into refusing to cooperate with any investigation relating to the use of such deadly force or induce another person to alter testimony about the use of such deadly force."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; matches Ellison's block quotation of subsection 2.

Excerpt read: 2. The person using deadly force shall not intentionally destroy, alter, conceal, or disguise physical evidence relating to the person's use of deadly force, and the person shall not intentionally intimidate witnesses

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-060: State v. Gibbs, 941 N.W.2d 888 (Iowa 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: In State v. Gibbs; pincite: .

Cited for: As-applied challenge to § 704.2B(1) instruction

Quotes: []

Context: Case-name reference followed by pin cite.

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-1298, Apr. 17, 2020). The majority states that the right against compulsory self-incrimination is protected by the Iowa due process clause (art. I, § 9), holds that an instruction authorizing an inference of guilt from breach of the § 704.2B(1) reporting duty penalized silence, refers to failure to 'affirmatively seek out the authorities and speak to them prearrest', expressly does not address § 704.2B(2), and says the jury holds it against the defendant 'in some significant but indeterminate way'. All quotations Ellison attributes to Gibbs appear. The slip has no N.W.2d page markers, so pins 894-900 could not be checked.

Excerpt read: A jury instruction authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities exacts a significant penalty on the defendant's right to remain silent. ... failing to affirmatively seek out the authorities and speak to them prearrest--with no Fifth Amendment exception. ... We do not address the constitutional ramifications of a jury instruction based only on section 704.2B(2).

- https://www.courtlistener.com/opinion/4746140/state-of-iowa-v-levi-gibbs-iii/

### Second check: not required


## ELLISON-061: Iowa Code § 704.2B(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 15 (slip op. at 15).

Authority type: statute; as written: section 704.2B(1); pincite: .

Cited for: Subject of Gibbs

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; matches Ellison's quotation of subsection 1.

Excerpt read: 1. If a person uses deadly force, the person shall notify or cause another to notify a law enforcement agency about the person's use of deadly force within a reasonable time period after the person's use of the deadly force, if the person or another person is capable of providing such notification.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-062: State v. Gibbs, 941 N.W.2d 888 (Iowa 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 15 (slip op. at 15).

Authority type: case; as written: 941 N.W.2d at 897; pincite: 897.

Cited for: Gibbs addressed § 704.2B(1) instruction

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-1298, Apr. 17, 2020). The majority states that the right against compulsory self-incrimination is protected by the Iowa due process clause (art. I, § 9), holds that an instruction authorizing an inference of guilt from breach of the § 704.2B(1) reporting duty penalized silence, refers to failure to 'affirmatively seek out the authorities and speak to them prearrest', expressly does not address § 704.2B(2), and says the jury holds it against the defendant 'in some significant but indeterminate way'. All quotations Ellison attributes to Gibbs appear. The slip has no N.W.2d page markers, so pins 894-900 could not be checked.

Excerpt read: A jury instruction authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities exacts a significant penalty on the defendant's right to remain silent. ... failing to affirmatively seek out the authorities and speak to them prearrest--with no Fifth Amendment exception. ... We do not address the constitutional ramifications of a jury instruction based only on section 704.2B(2).

- https://www.courtlistener.com/opinion/4746140/state-of-iowa-v-levi-gibbs-iii/

### Second check: not required


## ELLISON-063: Iowa Code § 704.2B(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 16 (slip op. at 16).

Authority type: statute; as written: Id. § 704.2B(1); pincite: .

Cited for: Statutory text

Quotes: ["If a person uses deadly force, the person shall notify or cause another to notify a law enforcement agency about the person's use of deadly force within a reasonable time period after the person's use of the deadly force, if the person or another person is capable of providing such notification."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; matches Ellison's quotation of subsection 1.

Excerpt read: 1. If a person uses deadly force, the person shall notify or cause another to notify a law enforcement agency about the person's use of deadly force within a reasonable time period after the person's use of the deadly force, if the person or another person is capable of providing such notification.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-064: State v. Gibbs, 941 N.W.2d 888 (Iowa 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 16 (slip op. at 16).

Authority type: case; as written: Gibbs, 941 N.W.2d at 897; pincite: 897.

Cited for: Instruction penalized right to remain silent

Quotes: ['authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-1298, Apr. 17, 2020). The majority states that the right against compulsory self-incrimination is protected by the Iowa due process clause (art. I, § 9), holds that an instruction authorizing an inference of guilt from breach of the § 704.2B(1) reporting duty penalized silence, refers to failure to 'affirmatively seek out the authorities and speak to them prearrest', expressly does not address § 704.2B(2), and says the jury holds it against the defendant 'in some significant but indeterminate way'. All quotations Ellison attributes to Gibbs appear. The slip has no N.W.2d page markers, so pins 894-900 could not be checked.

Excerpt read: A jury instruction authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities exacts a significant penalty on the defendant's right to remain silent. ... failing to affirmatively seek out the authorities and speak to them prearrest--with no Fifth Amendment exception. ... We do not address the constitutional ramifications of a jury instruction based only on section 704.2B(2).

- https://www.courtlistener.com/opinion/4746140/state-of-iowa-v-levi-gibbs-iii/

### Second check: not required


## ELLISON-065: Iowa Code § 704.2B(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 16 (slip op. at 16).

Authority type: statute; as written: Compare Iowa Code § 704.2B (1); pincite: .

Cited for: Duty to communicate

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; matches Ellison's quotation of subsection 1.

Excerpt read: 1. If a person uses deadly force, the person shall notify or cause another to notify a law enforcement agency about the person's use of deadly force within a reasonable time period after the person's use of the deadly force, if the person or another person is capable of providing such notification.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-066: Iowa Code § 704.2B(2)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 16 (slip op. at 16).

Authority type: statute; as written: with id. § 704.2B(2); pincite: .

Cited for: No similar duty

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; matches Ellison's block quotation of subsection 2.

Excerpt read: 2. The person using deadly force shall not intentionally destroy, alter, conceal, or disguise physical evidence relating to the person's use of deadly force, and the person shall not intentionally intimidate witnesses

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-067: State v. Gibbs, 941 N.W.2d 888 (Iowa 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 16 (slip op. at 16).

Authority type: case; as written: Gibbs, 941 N.W.2d at 898; pincite: 898.

Cited for: Unconstitutional penalty

Quotes: ['for failing to affirmatively seek out the authorities and speak to them prearrest—with no Fifth Amendment exception.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-1298, Apr. 17, 2020). The majority states that the right against compulsory self-incrimination is protected by the Iowa due process clause (art. I, § 9), holds that an instruction authorizing an inference of guilt from breach of the § 704.2B(1) reporting duty penalized silence, refers to failure to 'affirmatively seek out the authorities and speak to them prearrest', expressly does not address § 704.2B(2), and says the jury holds it against the defendant 'in some significant but indeterminate way'. All quotations Ellison attributes to Gibbs appear. The slip has no N.W.2d page markers, so pins 894-900 could not be checked.

Excerpt read: A jury instruction authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities exacts a significant penalty on the defendant's right to remain silent. ... failing to affirmatively seek out the authorities and speak to them prearrest--with no Fifth Amendment exception. ... We do not address the constitutional ramifications of a jury instruction based only on section 704.2B(2).

- https://www.courtlistener.com/opinion/4746140/state-of-iowa-v-levi-gibbs-iii/

### Second check: not required


## ELLISON-068: Iowa Code § 704.2B(2)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 16 (slip op. at 16).

Authority type: statute; as written: section 704.2B(2); pincite: .

Cited for: Not decided in Gibbs

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; matches Ellison's block quotation of subsection 2.

Excerpt read: 2. The person using deadly force shall not intentionally destroy, alter, conceal, or disguise physical evidence relating to the person's use of deadly force, and the person shall not intentionally intimidate witnesses

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-069: State v. Gibbs, 941 N.W.2d 888 (Iowa 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 16 (slip op. at 16).

Authority type: case; as written: Id. at 897 n.2; pincite: 897 n.2.

Cited for: Gibbs did not decide § 704.2B(2)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-1298, Apr. 17, 2020). The majority states that the right against compulsory self-incrimination is protected by the Iowa due process clause (art. I, § 9), holds that an instruction authorizing an inference of guilt from breach of the § 704.2B(1) reporting duty penalized silence, refers to failure to 'affirmatively seek out the authorities and speak to them prearrest', expressly does not address § 704.2B(2), and says the jury holds it against the defendant 'in some significant but indeterminate way'. All quotations Ellison attributes to Gibbs appear. The slip has no N.W.2d page markers, so pins 894-900 could not be checked.

Excerpt read: A jury instruction authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities exacts a significant penalty on the defendant's right to remain silent. ... failing to affirmatively seek out the authorities and speak to them prearrest--with no Fifth Amendment exception. ... We do not address the constitutional ramifications of a jury instruction based only on section 704.2B(2).

- https://www.courtlistener.com/opinion/4746140/state-of-iowa-v-levi-gibbs-iii/

### Second check: not required


## ELLISON-070: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 16 (slip op. at 16).

Authority type: constitution; as written: no Fifth Amendment problem; pincite: .

Cited for: State's argument

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## ELLISON-071: State v. Weiss, 528 N.W.2d 519 (Iowa 1995)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 17 (slip op. at 17).

Authority type: case; as written: State v. Weiss, 528 N.W.2d 519, 520 (Iowa 1995) (per curiam); pincite: 520.

Cited for: Ordinary words need not be defined

Quotes: ['need not be defined if they are of ordinary usage and are generally understood.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text (per curiam); the quoted rule appears verbatim.

Excerpt read: Words in an instruction need not be defined if they are of ordinary usage and are generally understood.

- https://www.courtlistener.com/opinion/2027842/state-v-weiss/

### Second check: not required


## ELLISON-072: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 17 (slip op. at 17).

Authority type: constitution; as written: Fifth Amendment concerns; pincite: .

Cited for: Dilemma raised by duty

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## ELLISON-073: State v. Gibbs, 941 N.W.2d 888 (Iowa 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 17 (slip op. at 17).

Authority type: case; as written: Gibbs, 941 N.W.2d at 898; pincite: 898.

Cited for: Same concerns

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-1298, Apr. 17, 2020). The majority states that the right against compulsory self-incrimination is protected by the Iowa due process clause (art. I, § 9), holds that an instruction authorizing an inference of guilt from breach of the § 704.2B(1) reporting duty penalized silence, refers to failure to 'affirmatively seek out the authorities and speak to them prearrest', expressly does not address § 704.2B(2), and says the jury holds it against the defendant 'in some significant but indeterminate way'. All quotations Ellison attributes to Gibbs appear. The slip has no N.W.2d page markers, so pins 894-900 could not be checked.

Excerpt read: A jury instruction authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities exacts a significant penalty on the defendant's right to remain silent. ... failing to affirmatively seek out the authorities and speak to them prearrest--with no Fifth Amendment exception. ... We do not address the constitutional ramifications of a jury instruction based only on section 704.2B(2).

- https://www.courtlistener.com/opinion/4746140/state-of-iowa-v-levi-gibbs-iii/

### Second check: not required


## ELLISON-074: State v. Decker, 744 N.W.2d 346 (Iowa 2008)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 17 (slip op. at 17).

Authority type: case; as written: See State v. Decker, 744 N.W.2d 346, 355 (Iowa 2008); pincite: 355.

Cited for: List of nontestimonial evidence

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Decker discusses testimonial versus nontestimonial evidence under the Fifth Amendment, supporting both Ellison citations (354 and 355). Pins not separately checked.

Excerpt read: It is axiomatic that only evidence that is testimonial in nature is protected by the Fifth Amendment. Nontestimonial evidence thus is unprotected

- https://www.courtlistener.com/opinion/2034889/state-v-decker/

### Second check: not required


## ELLISON-075: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 17 (slip op. at 17).

Authority type: constitution; as written: The Fifth Amendment's protections; pincite: .

Cited for: Extend to penalties on silence

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## ELLISON-076: State v. Gibbs, 941 N.W.2d 888 (Iowa 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 18 (slip op. at 18).

Authority type: case; as written: Gibbs, 941 N.W.2d at 894; pincite: 894.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-1298, Apr. 17, 2020). The majority states that the right against compulsory self-incrimination is protected by the Iowa due process clause (art. I, § 9), holds that an instruction authorizing an inference of guilt from breach of the § 704.2B(1) reporting duty penalized silence, refers to failure to 'affirmatively seek out the authorities and speak to them prearrest', expressly does not address § 704.2B(2), and says the jury holds it against the defendant 'in some significant but indeterminate way'. All quotations Ellison attributes to Gibbs appear. The slip has no N.W.2d page markers, so pins 894-900 could not be checked.

Excerpt read: A jury instruction authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities exacts a significant penalty on the defendant's right to remain silent. ... failing to affirmatively seek out the authorities and speak to them prearrest--with no Fifth Amendment exception. ... We do not address the constitutional ramifications of a jury instruction based only on section 704.2B(2).

- https://www.courtlistener.com/opinion/4746140/state-of-iowa-v-levi-gibbs-iii/

### Second check: not required


## ELLISON-077: Doe v. United States, 487 U.S. 201 (1988)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 18 (slip op. at 18).

Authority type: case; as written: In Doe v. United States ... 487 U.S. 201, 208–09 (1988); pincite: 208-09.

Cited for: Act of production may be testimonial

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the three quotations Ellison attributes to Doe (testimonial communication through implicit statements of fact; papers existed, were in possession or control, authentic; privilege applies to acts that imply assertions of fact) appear verbatim, citing United States v. Doe and Fisher.

Excerpt read: The Court concluded that the act of production could constitute protected testimonial communication because it might entail implicit statements of fact: by producing documents in compliance with a subpoena, the witness would admit that the papers existed, were in his possession or control, and were authentic. ... the Fifth Amendment privilege against self-incrimination applies to acts that imply assertions of fact.

- https://www.courtlistener.com/opinion/112123/doe-v-united-states/

### Second check: not required


## ELLISON-078: United States v. Doe, 465 U.S. 605 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 18 (slip op. at 18).

Authority type: case; as written: citing United States v. Doe, 465 U.S. 605 (1984); pincite: .

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the act of producing documents may be privileged even if contents are not.

Excerpt read: Although the contents of a document may not be privileged, the act of producing the document may be.

- https://www.courtlistener.com/opinion/111110/united-states-v-doe/

### Second check: not required


## ELLISON-079: Fisher v. United States, 425 U.S. 391 (1976)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 18 (slip op. at 18).

Authority type: case; as written: Fisher v. United States, 425 U.S. 391 (1976); pincite: .

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the act of producing evidence in response to a subpoena has communicative aspects of its own.

Excerpt read: The act of producing evidence in response to a subpoena nevertheless has communicative aspects of its own, wholly aside from the contents of the papers produced.

- https://www.courtlistener.com/opinion/109432/fisher-v-united-states/

### Second check: not required


## ELLISON-080: Doe v. United States, 487 U.S. 201 (1988)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 18 (slip op. at 18).

Authority type: case; as written: Id. [Doe]; pincite: 208-09.

Cited for: Act of production may entail implicit statements

Quotes: ['could constitute protected testimonial communication because it might entail implicit statements of fact.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the three quotations Ellison attributes to Doe (testimonial communication through implicit statements of fact; papers existed, were in possession or control, authentic; privilege applies to acts that imply assertions of fact) appear verbatim, citing United States v. Doe and Fisher.

Excerpt read: The Court concluded that the act of production could constitute protected testimonial communication because it might entail implicit statements of fact: by producing documents in compliance with a subpoena, the witness would admit that the papers existed, were in his possession or control, and were authentic. ... the Fifth Amendment privilege against self-incrimination applies to acts that imply assertions of fact.

- https://www.courtlistener.com/opinion/112123/doe-v-united-states/

### Second check: not required


## ELLISON-081: State v. Decker, 744 N.W.2d 346 (Iowa 2008)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 18 (slip op. at 18).

Authority type: case; as written: see also Decker, 744 N.W.2d at 354; pincite: 354.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Decker discusses testimonial versus nontestimonial evidence under the Fifth Amendment, supporting both Ellison citations (354 and 355). Pins not separately checked.

Excerpt read: It is axiomatic that only evidence that is testimonial in nature is protected by the Fifth Amendment. Nontestimonial evidence thus is unprotected

- https://www.courtlistener.com/opinion/2034889/state-v-decker/

### Second check: not required


## ELLISON-082: Doe v. United States, 487 U.S. 201 (1988)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 18 (slip op. at 18).

Authority type: case; as written: Doe, 487 U.S. at 208; pincite: 208.

Cited for: Production admits existence, possession, authenticity

Quotes: ['the witness would admit that the papers existed, were in his possession or control, and were authentic.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the three quotations Ellison attributes to Doe (testimonial communication through implicit statements of fact; papers existed, were in possession or control, authentic; privilege applies to acts that imply assertions of fact) appear verbatim, citing United States v. Doe and Fisher.

Excerpt read: The Court concluded that the act of production could constitute protected testimonial communication because it might entail implicit statements of fact: by producing documents in compliance with a subpoena, the witness would admit that the papers existed, were in his possession or control, and were authentic. ... the Fifth Amendment privilege against self-incrimination applies to acts that imply assertions of fact.

- https://www.courtlistener.com/opinion/112123/doe-v-united-states/

### Second check: not required


## ELLISON-083: Doe v. United States, 487 U.S. 201 (1988)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 18 (slip op. at 18).

Authority type: case; as written: Id. [Doe]; pincite: 208.

Cited for: Privilege applies to acts implying assertions of fact

Quotes: ['made clear that the Fifth Amendment privilege against self-incrimination applies to acts', 'that imply assertions of fact.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the three quotations Ellison attributes to Doe (testimonial communication through implicit statements of fact; papers existed, were in possession or control, authentic; privilege applies to acts that imply assertions of fact) appear verbatim, citing United States v. Doe and Fisher.

Excerpt read: The Court concluded that the act of production could constitute protected testimonial communication because it might entail implicit statements of fact: by producing documents in compliance with a subpoena, the witness would admit that the papers existed, were in his possession or control, and were authentic. ... the Fifth Amendment privilege against self-incrimination applies to acts that imply assertions of fact.

- https://www.courtlistener.com/opinion/112123/doe-v-united-states/

### Second check: not required


## ELLISON-084: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 18 (slip op. at 18).

Authority type: constitution; as written: Fifth Amendment concerns; pincite: .

Cited for: No assertion of fact implied

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## ELLISON-085: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 18 (slip op. at 18).

Authority type: constitution; as written: Ellison's Fifth Amendment privilege; pincite: .

Cited for: No violation

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## ELLISON-086: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF pages 18-19 (slip op. at 18-19).

Authority type: constitution; as written: Fifth Amendment rights; pincite: .

Cited for: No violation

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## ELLISON-087: U.S. Const. amend. XIV

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 19 (slip op. at 19).

Authority type: constitution; as written: the Fourteenth Amendment; pincite: .

Cited for: Incorporation

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fourteenth Amendment text at Cornell LII; § 1 contains the Due Process Clause through which Malloy incorporates the self-incrimination privilege.

Excerpt read: nor shall any State deprive any person of life, liberty, or property, without due process of law

- https://www.law.cornell.edu/constitution/amendmentxiv

### Second check: not required


## ELLISON-088: Iowa Code § 704.2B(2)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 19 (slip op. at 19).

Authority type: statute; as written: section 704.2B(2); pincite: .

Cited for: Instruction paraphrasing statute

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; matches Ellison's block quotation of subsection 2.

Excerpt read: 2. The person using deadly force shall not intentionally destroy, alter, conceal, or disguise physical evidence relating to the person's use of deadly force, and the person shall not intentionally intimidate witnesses

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-089: State v. Gibbs, 941 N.W.2d 888 (Iowa 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 19, footnote 2 (slip op. at 19 n.2).

Authority type: case; as written: In Gibbs ... 941 N.W.2d at 894–900; pincite: 894-900.

Cited for: Concerns about § 704.2B(1) instruction

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-1298, Apr. 17, 2020). The majority states that the right against compulsory self-incrimination is protected by the Iowa due process clause (art. I, § 9), holds that an instruction authorizing an inference of guilt from breach of the § 704.2B(1) reporting duty penalized silence, refers to failure to 'affirmatively seek out the authorities and speak to them prearrest', expressly does not address § 704.2B(2), and says the jury holds it against the defendant 'in some significant but indeterminate way'. All quotations Ellison attributes to Gibbs appear. The slip has no N.W.2d page markers, so pins 894-900 could not be checked.

Excerpt read: A jury instruction authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities exacts a significant penalty on the defendant's right to remain silent. ... failing to affirmatively seek out the authorities and speak to them prearrest--with no Fifth Amendment exception. ... We do not address the constitutional ramifications of a jury instruction based only on section 704.2B(2).

- https://www.courtlistener.com/opinion/4746140/state-of-iowa-v-levi-gibbs-iii/

### Second check: not required


## ELLISON-090: Iowa Code § 704.2B(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 19, footnote 2 (slip op. at 19 n.2).

Authority type: statute; as written: section 704.2B(1); pincite: .

Cited for: Subject of Gibbs concerns

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; matches Ellison's quotation of subsection 1.

Excerpt read: 1. If a person uses deadly force, the person shall notify or cause another to notify a law enforcement agency about the person's use of deadly force within a reasonable time period after the person's use of the deadly force, if the person or another person is capable of providing such notification.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-091: State v. Gibbs, 941 N.W.2d 888 (Iowa 2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 19, footnote 2 (slip op. at 19 n.2).

Authority type: case; as written: Id. at 899; pincite: 899.

Cited for: Jury holds it against defendant

Quotes: ['there can only be one answer—so the jury holds it against the defendant in some significan t but indeterminate way.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-1298, Apr. 17, 2020). The majority states that the right against compulsory self-incrimination is protected by the Iowa due process clause (art. I, § 9), holds that an instruction authorizing an inference of guilt from breach of the § 704.2B(1) reporting duty penalized silence, refers to failure to 'affirmatively seek out the authorities and speak to them prearrest', expressly does not address § 704.2B(2), and says the jury holds it against the defendant 'in some significant but indeterminate way'. All quotations Ellison attributes to Gibbs appear. The slip has no N.W.2d page markers, so pins 894-900 could not be checked.

Excerpt read: A jury instruction authorizing an inference of guilt in a murder case because the defendant breached a legal duty to make a report to authorities exacts a significant penalty on the defendant's right to remain silent. ... failing to affirmatively seek out the authorities and speak to them prearrest--with no Fifth Amendment exception. ... We do not address the constitutional ramifications of a jury instruction based only on section 704.2B(2).

- https://www.courtlistener.com/opinion/4746140/state-of-iowa-v-levi-gibbs-iii/

### Second check: not required


## ELLISON-092: Iowa Code § 704.2B

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 19, footnote 2 (slip op. at 19 n.2).

Authority type: statute; as written: section 704.2B; pincite: .

Cited for: Instructions under the section

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text of § 704.2B (duties after use of deadly force), referenced generally in Ellison n.2.

Excerpt read: 704.2B Use of deadly force -- duties -- evidence.

- https://www.legis.iowa.gov/docs/code/2020/704.pdf

### Second check: not required


## ELLISON-093: U.S. Const. amend. V

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 19, footnote 2 (slip op. at 19 n.2).

Authority type: constitution; as written: Fifth Amendment grounds; pincite: .

Cited for: Only ground raised

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Fifth Amendment text at Cornell LII; it contains the Double Jeopardy and Self-Incrimination Clauses referenced.

Excerpt read: nor shall any person be subject for the same offence to be twice put in jeopardy of life or limb; nor shall be compelled in any criminal case to be a witness against himself

- https://www.law.cornell.edu/constitution/fifth_amendment

### Second check: not required


## ELLISON-094: State v. Mitchell, 757 N.W.2d 431 (Iowa 2008)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Ellison.pdf; location: PDF page 19, footnote 2 (slip op. at 19 n.2).

Authority type: case; as written: State v. Mitchell, 757 N.W.2d 431, 435 (Iowa 2008); pincite: 435.

Cited for: Court declines to reach arguments not raised below

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Mitchell declines to reach an issue not raised and decided below (error preservation).

Excerpt read: "Issues not raised before the district court, including constitutional issues, cannot be raised for the first time on appeal." ... we determine that error was not preserved on Holly's due process claim

- https://www.courtlistener.com/opinion/1946978/state-v-mitchell/

### Second check: not required


## KUHSE-001: Iowa Code § 708.2A

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: Iowa Code sections 708.2A(1) [and 708.2A(2)(b)] (2017); pincite: .

Cited for: Domestic abuse assault causing bodily injury charge

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (domestic abuse assault). Kuhse cites the 2017 Code: subsection 1 defines domestic abuse assault, (2)(b) makes it a serious misdemeanor when it causes bodily injury, and (7)(a) sets a two-day minimum, consistent with Kuhse's description. The 2017 edition itself was not opened.

Excerpt read: 1. For the purposes of this chapter, "domestic abuse assault" means an assault, as defined in section 708.1, which is domestic abuse ... 2. ... b. A serious misdemeanor, if the domestic abuse assault causes bodily injury or mental illness. ... 7. a. A person convicted of violating subsection 2 or 3 shall serve a minimum term of two days

- https://www.legis.iowa.gov/docs/code/2020/708.2A.pdf

### Second check: not required


## KUHSE-002: Iowa Code § 708.2A

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 4 (slip op. at 4).

Authority type: statute; as written: [Iowa Code sections 708.2A(1) and] 708.2A(2)(b) (2017); pincite: .

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (domestic abuse assault). Kuhse cites the 2017 Code: subsection 1 defines domestic abuse assault, (2)(b) makes it a serious misdemeanor when it causes bodily injury, and (7)(a) sets a two-day minimum, consistent with Kuhse's description. The 2017 edition itself was not opened.

Excerpt read: 1. For the purposes of this chapter, "domestic abuse assault" means an assault, as defined in section 708.1, which is domestic abuse ... 2. ... b. A serious misdemeanor, if the domestic abuse assault causes bodily injury or mental illness. ... 7. a. A person convicted of violating subsection 2 or 3 shall serve a minimum term of two days

- https://www.legis.iowa.gov/docs/code/2020/708.2A.pdf

### Second check: not required


## KUHSE-003: Iowa Code § 708.2A

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 7 (slip op. at 7).

Authority type: statute; as written: See Iowa Code § 708.2A(7)(a); pincite: .

Cited for: Sentence imposed

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (domestic abuse assault). Kuhse cites the 2017 Code: subsection 1 defines domestic abuse assault, (2)(b) makes it a serious misdemeanor when it causes bodily injury, and (7)(a) sets a two-day minimum, consistent with Kuhse's description. The 2017 edition itself was not opened.

Excerpt read: 1. For the purposes of this chapter, "domestic abuse assault" means an assault, as defined in section 708.1, which is domestic abuse ... 2. ... b. A serious misdemeanor, if the domestic abuse assault causes bodily injury or mental illness. ... 7. a. A person convicted of violating subsection 2 or 3 shall serve a minimum term of two days

- https://www.legis.iowa.gov/docs/code/2020/708.2A.pdf

### Second check: not required


## KUHSE-004: Iowa Code § 903.1(1)(b)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 7 (slip op. at 7).

Authority type: statute; as written: id. § 903.1(1)(b); pincite: .

Cited for: Fine

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; the serious-misdemeanor minimum fine is $315, matching Kuhse's sentence.

Excerpt read: b. For a serious misdemeanor, there shall be a fine of at least three hundred fifteen dollars but not to exceed one thousand eight hundred seventy-five dollars.

- https://www.legis.iowa.gov/docs/code/2020/903.1.pdf

### Second check: not required


## KUHSE-005: Iowa Code § 911.1(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 7 (slip op. at 7).

Authority type: statute; as written: id. § 911.1(1); pincite: .

Cited for: Surcharge

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; criminal penalty surcharge on fines.

Excerpt read: When a court imposes a fine or forfeiture for a violation of state law ... the court or the clerk of the district court shall assess an additional penalty in the form of a criminal penalty surcharge

- https://www.legis.iowa.gov/docs/code/2020/911.1.pdf

### Second check: not required


## KUHSE-006: 2019 Iowa Acts ch. 140, § 31 (to be codified at Iowa Code § 814.7 (2020))

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 8 (slip op. at 8).

Authority type: statute; as written: 2019 Iowa Acts ch. 140, § 31 (to be codified at Iowa Code § 814.7 (2020)); pincite: .

Cited for: Code no longer permits IAC claims on direct appeal

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 Code § 814.7 (history: '2019 Acts, ch 140, §31'); it bars deciding ineffective-assistance claims on direct appeal. Macke (read) describes the same amendment and its July 1, 2019 effective date.

Excerpt read: An ineffective assistance of counsel claim in a criminal case shall be determined by filing an application for postconviction relief pursuant to chapter 822. ... the claim shall not be decided on direct appeal from the criminal proceedings. 2004 Acts, ch 1017, §2; 2019 Acts, ch 140, §31

- https://www.legis.iowa.gov/docs/code/2020/814.7.pdf

### Second check: not required


## KUHSE-007: State v. Macke, 933 N.W.2d 226 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: State v. Macke ... 933 N.W.2d 226, 228 (Iowa 2019); pincite: 228.

Cited for: Amendment does not apply to judgments entered before July 1, 2019

Quotes: ['do[es] not apply to a direct appeal from a judgment and sentence entered before July 1, 2019.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0839, Sept. 13, 2019); it holds amended §§ 814.6 and 814.7 do not apply to a direct appeal from a judgment and sentence entered before July 1, 2019. Kuhse's bracketed 'do[es]' adapts 'do'. Slip has no N.W.2d page markers; pin 228 not checked.

Excerpt read: we hold Iowa Code sections 814.6 and 814.7, as amended, do not apply to a direct appeal from a judgment and sentence entered before July 1, 2019.

- https://www.courtlistener.com/opinion/4660757/state-of-iowa-v-erin-macke/

### Second check: not required


## KUHSE-008: State v. Brothern, 832 N.W.2d 187 (Iowa 2013)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: State v. Brothern, 832 N.W.2d 187, 192 (Iowa 2013); pincite: 192.

Cited for: Record adequacy; otherwise preserve for postconviction

Quotes: ['Thus, we will decide whether the appellate record is adequate to determine the claim. If not, the claim will be preserved for postconviction relief.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Brothern states the court decides whether the record is adequate and, if not, preserves the claim for postconviction relief (quoting State v. Johnson), matching Kuhse's quotation.

Excerpt read: If not, the claim will be preserved for postconviction relief.

- https://www.courtlistener.com/opinion/4472222/state-of-iowa-v-anthony-george-brothern/

### Second check: not required


## KUHSE-009: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: See State v. Harris, 891 N.W.2d 182, 185–86 (Iowa 2017); pincite: 185-86.

Cited for: De novo review of IAC claim for failure to object to marshaling instruction

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-010: Iowa Code § 708.1(2)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 8 (slip op. at 8).

Authority type: statute; as written: Iowa Code § 708.1(2); pincite: .

Cited for: 'Justification' appears in assault definition

Quotes: ['[a] person commits an assault when, without justification, the person does any of the following . . . .']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; Kuhse's quotation matches. (Kuhse applied the 2017 Code; the quoted language is the same in the 2020 edition read.)

Excerpt read: 2. A person commits an assault when, without justification, the person does any of the following:

- https://www.legis.iowa.gov/docs/code/2020/708.1.pdf

### Second check: not required


## KUHSE-011: Iowa State Bar Ass'n, Iowa Criminal Jury Instruction 800.1 (2018)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 8 (slip op. at 8).

Authority type: other; as written: See Iowa State Bar Ass'n, Iowa Criminal Jury Instruction 800.1 (2018); pincite: .

Cited for: Model assault instruction omits justification language

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

The 2018 Iowa State Bar Association model instruction is not freely accessible; a web search found only paywalled listings of neighboring 800-series instructions. Kuhse's statement that 800.1 omits 'without justification' was not checked.

Excerpt read: 


### Second check: not required


## KUHSE-012: State v. Delay, 320 N.W.2d 831 (Iowa 1982)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 8 (slip op. at 8).

Authority type: case; as written: In State v. Delay ... 320 N.W.2d 831, 833 (Iowa 1982); pincite: 833.

Cited for: Justification is an affirmative defense, not an element

Quotes: ['justification is an affirmative defense rather than an element of that crime.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers. At 833 Delay holds justification is an affirmative defense rather than an element of assault; at 834 it states the defendant has the burden of going forward and the State has no burden to negate the defense unless the defendant meets the initial burden of producing sufficient evidence, and gives the 'laboriously disproving' rationale; at 834-35 it holds the trial court properly refused a self-defense instruction where no evidence generated a jury question. Supports each Kuhse citation (833, 834, 835).

Excerpt read: We believe, however, that justification is an affirmative defense rather than an element of that crime. [*834] ... it is the defendant who has the burden of going forward with evidence of an affirmative defense. There is no burden on the State to negate an affirmative defense unless the defendant meets his initial burden by producing sufficient evidence that the defense applies. ... It is unreasonable to think that the legislature intended to place upon the State the burden of laboriously disproving each of those forms of justification in every prosecution for assault, no matter how unrelated to the facts of the case they may be.

- https://www.courtlistener.com/opinion/1752241/state-v-delay/

### Second check: not required


## KUHSE-013: State v. Delay, 320 N.W.2d 831 (Iowa 1982)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF pages 8-9 (slip op. at 8-9).

Authority type: case; as written: Id. at 834; pincite: 834.

Cited for: Rationale

Quotes: ['It is unreasonable to think that the legislature intended to place upon the State the burden of laboriously disproving each of those forms of justification in every prosecution for assault, no matter how unrelated to the facts of the case they may be.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers. At 833 Delay holds justification is an affirmative defense rather than an element of assault; at 834 it states the defendant has the burden of going forward and the State has no burden to negate the defense unless the defendant meets the initial burden of producing sufficient evidence, and gives the 'laboriously disproving' rationale; at 834-35 it holds the trial court properly refused a self-defense instruction where no evidence generated a jury question. Supports each Kuhse citation (833, 834, 835).

Excerpt read: We believe, however, that justification is an affirmative defense rather than an element of that crime. [*834] ... it is the defendant who has the burden of going forward with evidence of an affirmative defense. There is no burden on the State to negate an affirmative defense unless the defendant meets his initial burden by producing sufficient evidence that the defense applies. ... It is unreasonable to think that the legislature intended to place upon the State the burden of laboriously disproving each of those forms of justification in every prosecution for assault, no matter how unrelated to the facts of the case they may be.

- https://www.courtlistener.com/opinion/1752241/state-v-delay/

### Second check: not required


## KUHSE-014: State v. Delay, 320 N.W.2d 831 (Iowa 1982)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: Id. at 835; pincite: 835.

Cited for: Court must instruct on justification if substantial evidence supports it

Quotes: []

Context: Page 9 is the 'slip op. at 9' cited in assignment 2 criteria 1, 2 and 10.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers. At 833 Delay holds justification is an affirmative defense rather than an element of assault; at 834 it states the defendant has the burden of going forward and the State has no burden to negate the defense unless the defendant meets the initial burden of producing sufficient evidence, and gives the 'laboriously disproving' rationale; at 834-35 it holds the trial court properly refused a self-defense instruction where no evidence generated a jury question. Supports each Kuhse citation (833, 834, 835).

Excerpt read: We believe, however, that justification is an affirmative defense rather than an element of that crime. [*834] ... it is the defendant who has the burden of going forward with evidence of an affirmative defense. There is no burden on the State to negate an affirmative defense unless the defendant meets his initial burden by producing sufficient evidence that the defense applies. ... It is unreasonable to think that the legislature intended to place upon the State the burden of laboriously disproving each of those forms of justification in every prosecution for assault, no matter how unrelated to the facts of the case they may be.

- https://www.courtlistener.com/opinion/1752241/state-v-delay/

### Second check: not required


## KUHSE-015: State v. Delay, 320 N.W.2d 831 (Iowa 1982)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: Id. at 834; pincite: 834.

Cited for: Defendant bears initial burden of producing sufficient evidence to support the instruction

Quotes: []

Context: Immediately precedes 'Once that threshold is met, the burden shifts to the State' (no citation follows that sentence).

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers. At 833 Delay holds justification is an affirmative defense rather than an element of assault; at 834 it states the defendant has the burden of going forward and the State has no burden to negate the defense unless the defendant meets the initial burden of producing sufficient evidence, and gives the 'laboriously disproving' rationale; at 834-35 it holds the trial court properly refused a self-defense instruction where no evidence generated a jury question. Supports each Kuhse citation (833, 834, 835).

Excerpt read: We believe, however, that justification is an affirmative defense rather than an element of that crime. [*834] ... it is the defendant who has the burden of going forward with evidence of an affirmative defense. There is no burden on the State to negate an affirmative defense unless the defendant meets his initial burden by producing sufficient evidence that the defense applies. ... It is unreasonable to think that the legislature intended to place upon the State the burden of laboriously disproving each of those forms of justification in every prosecution for assault, no matter how unrelated to the facts of the case they may be.

- https://www.courtlistener.com/opinion/1752241/state-v-delay/

### Second check: not required


## KUHSE-016: U.S. Const. amend. VI

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 9 (slip op. at 9).

Authority type: constitution; as written: U.S. Const. amend. VI; pincite: .

Cited for: Right to effective assistance of counsel

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Sixth Amendment text at Cornell LII; it guarantees confrontation and the assistance of counsel.

Excerpt read: to be confronted with the witnesses against him; ... and to have the Assistance of Counsel for his defence.

- https://www.law.cornell.edu/constitution/sixth_amendment

### Second check: not required


## KUHSE-017: Iowa Const. art. I, § 10

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 9 (slip op. at 9).

Authority type: constitution; as written: Iowa Const. art. I, § 10; pincite: .

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the codified Iowa Constitution published by the Iowa Legislature; article I, section 10 guarantees the accused the assistance of counsel.

Excerpt read: SEC. 10. In all criminal prosecutions, ... the accused shall have a right to ... the assistance of counsel.

- https://www.legis.iowa.gov/docs/publications/icnst/402726.pdf

### Second check: not required


## KUHSE-018: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: Strickland v. Washington, 466 U.S. 668, 687–88, 104 S. Ct. 2052, 2064–65 (1984); pincite: 687-88.

Cited for: Two-prong IAC test

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-019: Ledezma v. State, 626 N.W.2d 134 (Iowa 2001)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: Ledezma v. State, 626 N.W.2d 134, 141–42, 145 (Iowa 2001) (en banc); pincite: 141-42, 145.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers; Part IV ('Overview of the Law Governing Ineffective Assistance of Counsel Claims') begins at 142 and sets out the Strickland duty and prejudice prongs through 145. Kuhse's 141-42 pin starts one page early.

Excerpt read: [*142] ... IV. Ineffective Assistance of Counsel. A. Overview of the Law Governing Ineffective Assistance of Counsel Claims. ... an applicant must meet "the burden of showing that the decision reached would reasonably likely [*144] have been different absent the errors."

- https://www.courtlistener.com/opinion/1611878/ledezma-v-state/

### Second check: not required


## KUHSE-020: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: Strickland, 466 U.S. at 687, 104 S. Ct. at 2064; pincite: 687.

Cited for: Deficient performance

Quotes: ["must show that counsel's performance was deficient,", "made errors so serious that counsel was not functioning as the 'counsel' guaranteed the defendant by the Sixth Amendment."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-021: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: Id. at 688, 104 S. Ct. at 2065 [Strickland]; pincite: 688.

Cited for: Reasonableness under all circumstances

Quotes: ["whether counsel's assistance was reasonable considering all the circumstances."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-022: Nguyen v. State, 878 N.W.2d 744 (Iowa 2016)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 9 (slip op. at 9).

Authority type: case; as written: see Nguyen v. State, 878 N.W.2d 744, 752 (Iowa 2016); pincite: 752.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Nguyen reserves the right to interpret the Iowa Constitution differently even where parties advance no different standard, and applies the federal framework where no distinction is argued; it also restates the Strickland two-prong test (the proposition for which Kuhse cites it at 752). Pins not separately checked.

Excerpt read: "Even in these cases in which no substantive distinction had been made between state and federal constitutional provisions, we reserve the right to apply the principles differently under the state constitution compared to its federal counterpart."

- https://www.courtlistener.com/opinion/3184687/phuoc-nguyen-v-state-of-iowa/

### Second check: not required


## KUHSE-023: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF pages 9-10 (slip op. at 9-10).

Authority type: case; as written: Strickland, 466 U.S. at 694, 104 S. Ct. at 2068; pincite: 694.

Cited for: Prejudice standard

Quotes: ["that there is a reasonable probability that, but for counsel's unprofessional errors, the result of the proceeding would have been different. A reasonable probability is a probability sufficient to undermine confidence in the outcome."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-024: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: see State v. Lorenzo Baltazar, 935 N.W.2d 862, 872 (Iowa 2019); pincite: 872.

Cited for: No prejudice from outdated instruction given overwhelming evidence

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## KUHSE-025: State v. Ambrose, 861 N.W.2d 550 (Iowa 2015)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: State v. Ambrose, 861 N.W.2d 550, 557–59 (Iowa 2015); pincite: 557-59.

Cited for: Prejudice standard (block quotation)

Quotes: ['The likelihood of a different result must be substantial, not just conceivable.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the block quotation in Kuhse appears (Ambrose citing King and Clay).

Excerpt read: To establish prejudice in the context of an ineffective-assistance-of-counsel claim, a defendant must show a reasonable probability that the result of the trial would have been different. ... The likelihood of a different result must be substantial, not just conceivable. ... A defendant must show the probability of a different result is sufficient to undermine confidence in the outcome.

- https://www.courtlistener.com/opinion/2766188/state-of-iowa-v-kevin-deshay-ambrose/

### Second check: not required


## KUHSE-026: State v. Fintel, 689 N.W.2d 95 (Iowa 2004)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: State v. Fintel, 689 N.W.2d 95, 104 (Iowa 2004); pincite: 104.

Cited for: Instructions considered as a whole

Quotes: ['Jury instructions are not considered separately; they should be considered as a whole.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers; at 103 the defendant challenges instructions telling the jury to determine his 'guilt or innocence', and after the *104 marker the court states instructions are considered as a whole and finds no prejudice given the burden and reasonable-doubt instructions.

Excerpt read: Defendant maintains Instructions 2, 4, and 5 are improper because they instruct the jury to determine his guilt or innocence. ... Jury instructions are not considered separately; they should be considered as a whole.

- https://www.courtlistener.com/opinion/2100441/state-v-fintel/

### Second check: not required


## KUHSE-027: State v. Fintel, 689 N.W.2d 95 (Iowa 2004)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: In Fintel ... Id. at 103; pincite: 103.

Cited for: Fintel's IAC claim on three instructions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers; at 103 the defendant challenges instructions telling the jury to determine his 'guilt or innocence', and after the *104 marker the court states instructions are considered as a whole and finds no prejudice given the burden and reasonable-doubt instructions.

Excerpt read: Defendant maintains Instructions 2, 4, and 5 are improper because they instruct the jury to determine his guilt or innocence. ... Jury instructions are not considered separately; they should be considered as a whole.

- https://www.courtlistener.com/opinion/2100441/state-v-fintel/

### Second check: not required


## KUHSE-028: State v. Fintel, 689 N.W.2d 95 (Iowa 2004)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: Id. (emphasis added) [Fintel at 103]; pincite: 103.

Cited for: Instructions directed jury to determine guilt or innocence

Quotes: ['to determine his guilt or innocence.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers; at 103 the defendant challenges instructions telling the jury to determine his 'guilt or innocence', and after the *104 marker the court states instructions are considered as a whole and finds no prejudice given the burden and reasonable-doubt instructions.

Excerpt read: Defendant maintains Instructions 2, 4, and 5 are improper because they instruct the jury to determine his guilt or innocence. ... Jury instructions are not considered separately; they should be considered as a whole.

- https://www.courtlistener.com/opinion/2100441/state-v-fintel/

### Second check: not required


## KUHSE-029: State v. Fintel, 689 N.W.2d 95 (Iowa 2004)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 10 (slip op. at 10).

Authority type: case; as written: Id. at 103–04; pincite: 103-04.

Cited for: No prejudice given burden and reasonable-doubt instructions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers; at 103 the defendant challenges instructions telling the jury to determine his 'guilt or innocence', and after the *104 marker the court states instructions are considered as a whole and finds no prejudice given the burden and reasonable-doubt instructions.

Excerpt read: Defendant maintains Instructions 2, 4, and 5 are improper because they instruct the jury to determine his guilt or innocence. ... Jury instructions are not considered separately; they should be considered as a whole.

- https://www.courtlistener.com/opinion/2100441/state-v-fintel/

### Second check: not required


## KUHSE-030: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF pages 10-11 (slip op. at 10-11).

Authority type: case; as written: See Lorenzo Baltazar, 935 N.W.2d at 871–72; pincite: 871-72.

Cited for: Standards differ for preserved vs IAC instruction error

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## KUHSE-031: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Id. at 871; pincite: 871.

Cited for: Presumed prejudice for preserved errors

Quotes: ['presumed-prejudice standard applies to preserved errors in jury instructions.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## KUHSE-032: State v. Lorenzo Baltazar, 935 N.W.2d 862 (Iowa 2019)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Id. at 871–72; pincite: 871-72.

Cited for: IAC claim requires deficiency and prejudice

Quotes: ['an ineffective-assistance-of- counsel claim based on failure to preserve jury instruction error must demonstrate deficiency and prejudice.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the CourtListener slip opinion (No. 18-0677, Nov. 22, 2019). It holds the 2017 amendment changed but did not eliminate the implied duty to follow an alternative course of action, that the duty remains for a person engaged in illegal activity, that Baltazar's handgun possession was germane to the use of force and disqualified him from the stand-your-ground instruction (so no ineffective assistance), that the presumed-prejudice standard applies to preserved instruction error while unpreserved error raised as ineffective assistance requires deficiency and prejudice, and that overwhelming evidence defeated prejudice from the outdated instruction. CourtListener holds only the slip opinion (no N.W.2d page markers), so the 870/871/872 pins could not be checked; the reporter citation 935 N.W.2d 862 is the one used by the Iowa Supreme Court in Ellison and Kuhse.

Excerpt read: We agree the 2017 amendment changed--but did not eliminate--the implied duty to follow an alternative course of action. If there is no duty to retreat when a person is not engaged in illegal activity or lawfully present, then by implication the duty to retreat remains if the activity is illegal or the presence unlawful. ... Even assuming the implied duty to retreat involves only illegal activities germane to the use of force, Baltazar's possession of the handgun was directly related to the shooting death of Mercado. ... the presumed-prejudice standard applies to preserved errors in jury instructions.

- https://www.courtlistener.com/opinion/4680966/state-of-iowa-v-miguel-angel-lorenzo-baltazar/

### Second check: not required


## KUHSE-033: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Harris, 891 N.W.2d 182; pincite: .

Cited for: Example of IAC for omitted element

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-034: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Id. at 184; pincite: 184.

Cited for: Facts

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-035: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Id. at 185; pincite: 185.

Cited for: Conviction for going armed

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-036: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Id.; pincite: 185.

Cited for: Marshaling instruction omitted element

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-037: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Id.; pincite: 185.

Cited for: Defendant's IAC argument

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-038: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Id. at 187; pincite: 187.

Cited for: Reasonable fact finder could find movement

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-039: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: See id. at 187–89; pincite: 187-89.

Cited for: Not dispositive

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-040: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Id. at 189; pincite: 189.

Cited for: Substantial evidence does not control prejudice

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-041: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Id. at 188; pincite: 188.

Cited for: Apply prejudice framework

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-042: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Id. at 189; pincite: 189.

Cited for: Confidence undermined

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-043: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 11 (slip op. at 11).

Authority type: case; as written: Harris illustrates; pincite: .

Cited for: Particularized review needed

Quotes: []

Context: Case-name reference.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-044: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: Harris is consistent with prior law; pincite: .

Cited for: Same

Quotes: []

Context: Case-name reference.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-045: State v. Propps, 376 N.W.2d 619 (Iowa 1985)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: In State v. Propps ... 376 N.W.2d 619, 623 (Iowa 1985); pincite: 623.

Cited for: No IAC for omitted knowledge element

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; just before the *624 marker (at 623) the court notes the instructions elsewhere supplied the missing knowledge element and that 'The State is on firm ground in arguing the defendant has shown no prejudice.' (The 'does not contend the instruction ... was proper' sentence was not separately searched.)

Excerpt read: It is to be noted that the instructions elsewhere supplied the missing element. ... The State is on firm ground in arguing the defendant has shown no prejudice.

- https://www.courtlistener.com/opinion/1756603/state-v-propps/

### Second check: not required


## KUHSE-046: State v. Propps, 376 N.W.2d 619 (Iowa 1985)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: Id. [Propps]; pincite: 623.

Cited for: State did not defend instruction

Quotes: ['The State does not contend the instruction, as it related to knowledge, was proper.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; just before the *624 marker (at 623) the court notes the instructions elsewhere supplied the missing knowledge element and that 'The State is on firm ground in arguing the defendant has shown no prejudice.' (The 'does not contend the instruction ... was proper' sentence was not separately searched.)

Excerpt read: It is to be noted that the instructions elsewhere supplied the missing element. ... The State is on firm ground in arguing the defendant has shown no prejudice.

- https://www.courtlistener.com/opinion/1756603/state-v-propps/

### Second check: not required


## KUHSE-047: State v. Propps, 376 N.W.2d 619 (Iowa 1985)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: Id. [Propps]; pincite: 623.

Cited for: No prejudice

Quotes: ['The State is on firm ground in arguing the defendant has shown no prejudice.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; just before the *624 marker (at 623) the court notes the instructions elsewhere supplied the missing knowledge element and that 'The State is on firm ground in arguing the defendant has shown no prejudice.' (The 'does not contend the instruction ... was proper' sentence was not separately searched.)

Excerpt read: It is to be noted that the instructions elsewhere supplied the missing element. ... The State is on firm ground in arguing the defendant has shown no prejudice.

- https://www.courtlistener.com/opinion/1756603/state-v-propps/

### Second check: not required


## KUHSE-048: State v. Propps, 376 N.W.2d 619 (Iowa 1985)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: Id. [Propps]; pincite: 623.

Cited for: Instructions elsewhere supplied element

Quotes: ['the instructions elsewhere supplied the missing element.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; just before the *624 marker (at 623) the court notes the instructions elsewhere supplied the missing knowledge element and that 'The State is on firm ground in arguing the defendant has shown no prejudice.' (The 'does not contend the instruction ... was proper' sentence was not separately searched.)

Excerpt read: It is to be noted that the instructions elsewhere supplied the missing element. ... The State is on firm ground in arguing the defendant has shown no prejudice.

- https://www.courtlistener.com/opinion/1756603/state-v-propps/

### Second check: not required


## KUHSE-049: State v. Douglas, 485 N.W.2d 619 (Iowa 1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: In State v. Douglas ... 485 N.W.2d 619, 621–22 (Iowa 1992); pincite: 621-22.

Cited for: No IAC for felony-murder instructions

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Douglas rejects the ineffective-assistance claim because expert testimony 'belies the suggestion of a nexus' between the acts and epilepsy and because Douglas 'received the benefit of this defense' through other instructions, matching Kuhse's bracketed quotations.

Excerpt read: First, the expert testimony by Dr. Fortson belies the suggestion of a nexus between Douglas's acts and his condition of epilepsy. ... Second, we believe Douglas received the benefit of this defense as to the felony murder count through other instructions by the court.

- https://www.courtlistener.com/opinion/1599736/state-v-douglas/

### Second check: not required


## KUHSE-050: State v. Douglas, 485 N.W.2d 619 (Iowa 1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: Id. [Douglas]; pincite: 621-22.

Cited for: Diminished responsibility raised

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Douglas rejects the ineffective-assistance claim because expert testimony 'belies the suggestion of a nexus' between the acts and epilepsy and because Douglas 'received the benefit of this defense' through other instructions, matching Kuhse's bracketed quotations.

Excerpt read: First, the expert testimony by Dr. Fortson belies the suggestion of a nexus between Douglas's acts and his condition of epilepsy. ... Second, we believe Douglas received the benefit of this defense as to the felony murder count through other instructions by the court.

- https://www.courtlistener.com/opinion/1599736/state-v-douglas/

### Second check: not required


## KUHSE-051: State v. Douglas, 485 N.W.2d 619 (Iowa 1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: Id. [Douglas] (after block quotation); pincite: 621-22.

Cited for: Trial-court account

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Douglas rejects the ineffective-assistance claim because expert testimony 'belies the suggestion of a nexus' between the acts and epilepsy and because Douglas 'received the benefit of this defense' through other instructions, matching Kuhse's bracketed quotations.

Excerpt read: First, the expert testimony by Dr. Fortson belies the suggestion of a nexus between Douglas's acts and his condition of epilepsy. ... Second, we believe Douglas received the benefit of this defense as to the felony murder count through other instructions by the court.

- https://www.courtlistener.com/opinion/1599736/state-v-douglas/

### Second check: not required


## KUHSE-052: State v. Douglas, 485 N.W.2d 619 (Iowa 1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: Id. at 622; pincite: 622.

Cited for: Expert testimony belied nexus

Quotes: ["belie[d] the suggestion of a nexus between [the defendant's] acts and his condition of epilepsy."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Douglas rejects the ineffective-assistance claim because expert testimony 'belies the suggestion of a nexus' between the acts and epilepsy and because Douglas 'received the benefit of this defense' through other instructions, matching Kuhse's bracketed quotations.

Excerpt read: First, the expert testimony by Dr. Fortson belies the suggestion of a nexus between Douglas's acts and his condition of epilepsy. ... Second, we believe Douglas received the benefit of this defense as to the felony murder count through other instructions by the court.

- https://www.courtlistener.com/opinion/1599736/state-v-douglas/

### Second check: not required


## KUHSE-053: State v. Douglas, 485 N.W.2d 619 (Iowa 1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 12 (slip op. at 12).

Authority type: case; as written: Id. [Douglas at 622]; pincite: 622.

Cited for: Benefit of defense through other instructions

Quotes: ['received the benefit of this defense [diminished capacity] through other instructions by the court.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Douglas rejects the ineffective-assistance claim because expert testimony 'belies the suggestion of a nexus' between the acts and epilepsy and because Douglas 'received the benefit of this defense' through other instructions, matching Kuhse's bracketed quotations.

Excerpt read: First, the expert testimony by Dr. Fortson belies the suggestion of a nexus between Douglas's acts and his condition of epilepsy. ... Second, we believe Douglas received the benefit of this defense as to the felony murder count through other instructions by the court.

- https://www.courtlistener.com/opinion/1599736/state-v-douglas/

### Second check: not required


## KUHSE-054: State v. Heacock, 521 N.W.2d 707 (Iowa 1994)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: In State v. Heacock ... 521 N.W.2d 707, 709 (Iowa 1994); pincite: 709.

Cited for: Marshaling instruction missing specific-intent element

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Kuhse's block quotation straddles the *710 marker (709-10) and matches.

Excerpt read: Had it been preserved by objection, Heacock's [*710] claimed error may have demanded reversal. But error was not preserved and the fundamental rule is that it was therefore waived.

- https://www.courtlistener.com/opinion/1969236/state-v-heacock/

### Second check: not required


## KUHSE-055: State v. Heacock, 521 N.W.2d 707 (Iowa 1994)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: Id. at 709–10; pincite: 709-10.

Cited for: Block quotation rejecting claim

Quotes: ["Had it been preserved by objection, Heacock's claimed error may have demanded reversal. But error was not preserved and the fundamental rule is that it was therefore waived."]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Kuhse's block quotation straddles the *710 marker (709-10) and matches.

Excerpt read: Had it been preserved by objection, Heacock's [*710] claimed error may have demanded reversal. But error was not preserved and the fundamental rule is that it was therefore waived.

- https://www.courtlistener.com/opinion/1969236/state-v-heacock/

### Second check: not required


## KUHSE-056: State v. Harris, 891 N.W.2d 182 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: under cases like Harris; pincite: .

Cited for: Synthesis

Quotes: []

Context: Case-name reference.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text with page markers (*184, *185 ...). Harris explains that the 'going' element of going armed with intent requires proof of movement; the marshaling instruction omitted that element; counsel's failure to object is analyzed under the Strickland prejudice framework; and the court found prejudice. Supports Ellison (at 186) and Kuhse's description (184-89).

Excerpt read: We have also explained that the "going" element of going armed with intent "necessarily implicates proof of movement." ... Notably, this instruction did not include the element of going or moving with the specific intent to use [the knife] against [the victim].

- https://www.courtlistener.com/opinion/4370915/state-of-iowa-v-james-norman-harris/

### Second check: not required


## KUHSE-057: State v. Propps, 376 N.W.2d 619 (Iowa 1985)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: Propps; pincite: .

Cited for: Synthesis

Quotes: []

Context: Case-name reference.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; just before the *624 marker (at 623) the court notes the instructions elsewhere supplied the missing knowledge element and that 'The State is on firm ground in arguing the defendant has shown no prejudice.' (The 'does not contend the instruction ... was proper' sentence was not separately searched.)

Excerpt read: It is to be noted that the instructions elsewhere supplied the missing element. ... The State is on firm ground in arguing the defendant has shown no prejudice.

- https://www.courtlistener.com/opinion/1756603/state-v-propps/

### Second check: not required


## KUHSE-058: State v. Douglas, 485 N.W.2d 619 (Iowa 1992)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: Douglas; pincite: .

Cited for: Synthesis

Quotes: []

Context: Case-name reference.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Douglas rejects the ineffective-assistance claim because expert testimony 'belies the suggestion of a nexus' between the acts and epilepsy and because Douglas 'received the benefit of this defense' through other instructions, matching Kuhse's bracketed quotations.

Excerpt read: First, the expert testimony by Dr. Fortson belies the suggestion of a nexus between Douglas's acts and his condition of epilepsy. ... Second, we believe Douglas received the benefit of this defense as to the felony murder count through other instructions by the court.

- https://www.courtlistener.com/opinion/1599736/state-v-douglas/

### Second check: not required


## KUHSE-059: State v. Heacock, 521 N.W.2d 707 (Iowa 1994)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 13 (slip op. at 13).

Authority type: case; as written: and Heacock; pincite: .

Cited for: Synthesis

Quotes: []

Context: Case-name reference.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Kuhse's block quotation straddles the *710 marker (709-10) and matches.

Excerpt read: Had it been preserved by objection, Heacock's [*710] claimed error may have demanded reversal. But error was not preserved and the fundamental rule is that it was therefore waived.

- https://www.courtlistener.com/opinion/1969236/state-v-heacock/

### Second check: not required


## KUHSE-060: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 14 (slip op. at 14).

Authority type: case; as written: Strickland prejudice; pincite: .

Cited for: Kuhse cannot establish prejudice

Quotes: []

Context: Case name used as doctrine label.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-061: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16 (slip op. at 16) (Appel, J., concurring specially).

Authority type: case; as written: Strickland v. Washington, 466 U.S. 668, 104 S. Ct. 2052 (1984); pincite: .

Cited for: Two-pronged IAC test

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-062: U.S. Const. amend. VI

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 3 (Appel, J., concurring specially).

Authority type: constitution; as written: the Sixth Amendment to the United States Constitution; pincite: .

Cited for: Not cited by Kuhse

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the Sixth Amendment text at Cornell LII; it guarantees confrontation and the assistance of counsel.

Excerpt read: to be confronted with the witnesses against him; ... and to have the Assistance of Counsel for his defence.

- https://www.law.cornell.edu/constitution/sixth_amendment

### Second check: not required


## KUHSE-063: Iowa Const. art. I, § 10

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 3 (Appel, J., concurring specially).

Authority type: constitution; as written: article I, section 10 of the Iowa Constitution; pincite: .

Cited for: Not cited by Kuhse

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the codified Iowa Constitution published by the Iowa Legislature; article I, section 10 guarantees the accused the assistance of counsel.

Excerpt read: SEC. 10. In all criminal prosecutions, ... the accused shall have a right to ... the assistance of counsel.

- https://www.legis.iowa.gov/docs/publications/icnst/402726.pdf

### Second check: not required


## KUHSE-064: King v. State, 797 N.W.2d 565 (Iowa 2011)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 3 (Appel, J., concurring specially).

Authority type: case; as written: King v. State, 797 N.W.2d 565, 571 (Iowa 2011); pincite: 571.

Cited for: Court may consider both provisions when neither cited

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; where a party does not indicate whether a claim rests on the Sixth Amendment or article I, section 10, the court regards both as preserved (consistent with Kuhse n.3; pin 571 not separately checked).

Excerpt read: When there are parallel constitutional provisions in the federal and state constitutions and a party does not indicate the specific constitutional basis, we regard both federal and state constitutional claims as preserved

- https://www.courtlistener.com/opinion/4472446/daniel-king-v-state-of-iowa/

### Second check: not required


## KUHSE-065: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 3 (Appel, J., concurring specially).

Authority type: case; as written: Strickland's principles; pincite: .

Cited for: Adopted by Kuhse

Quotes: []

Context: Case name used as doctrine label.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-066: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 3 (Appel, J., concurring specially).

Authority type: case; as written: the Strickland test; pincite: .

Cited for: Applied for purposes of the case

Quotes: []

Context: Case name used as doctrine label.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-067: State v. Graham, 897 N.W.2d 476 (Iowa 2017)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 3 (Appel, J., concurring specially).

Authority type: case; as written: See, e.g., State v. Graham, 897 N.W.2d 476, 481 (Iowa 2017); pincite: 481.

Cited for: Iowa need not apply federal standards identically

Quotes: ['[W]e do not necessarily apply the federal standards in a fashion identical to the United States Supreme Court.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted sentence appears verbatim.

Excerpt read: Even so, we do not necessarily apply the federal standards in a fashion identical to the United States Supreme Court.

- https://www.courtlistener.com/opinion/4394393/state-of-iowa-v-bradley-steven-graham/

### Second check: not required


## KUHSE-068: State v. Lindsey, 881 N.W.2d 411 (Iowa 2016)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 3 (Appel, J., concurring specially).

Authority type: case; as written: State v. Lindsey, 881 N.W.2d 411, 427 (Iowa 2016); pincite: 427.

Cited for: Reserve right to apply framework differently

Quotes: ['we apply the federal framework for the purpose of this case', 'reserve the right to apply that framework in a fashion different from federal caselaw']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener lead-opinion text; the quoted language appears ('we apply the federal framework for the purpose of this case but reserve the right to apply that framework in a fashion different from federal caselaw'). Pin 427 not separately checked.

Excerpt read: Because Lindsey has not suggested an independent standard under the Iowa Constitution, we apply the federal framework for the purpose of this case but reserve the right to apply that framework in a fashion different from federal caselaw

- https://www.courtlistener.com/opinion/3216871/state-of-iowa-v-maryo-d-lindsey-jr/

### Second check: not required


## KUHSE-069: State v. Pals, 805 N.W.2d 767 (Iowa 2011)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 3 (Appel, J., concurring specially).

Authority type: case; as written: State v. Pals, 805 N.W.2d 767, 771–72 (Iowa 2011); pincite: 771-72.

Cited for: May apply standard more stringently

Quotes: ['Even where a party has not advanced a different standard for interpreting a state constitutional provision, we may apply the standard more stringently than federal case law.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the quoted sentence straddles the *772 marker (771-72).

Excerpt read: [Even where a party has] [*772] not advanced a different standard for interpreting a state constitutional provision, we may apply the standard more stringently than federal case law.

- https://www.courtlistener.com/opinion/4472392/state-of-iowa-v-randall-lee-pals/

### Second check: not required


## KUHSE-070: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 4 (Appel, J., concurring specially).

Authority type: case; as written: Strickland, 466 U.S. at 707, 104 S. Ct. at 2075 (Marshall, J., dissenting); pincite: 707.

Cited for: Test is malleable

Quotes: ['so malleable that, in practice, it . . . [has] no grip', 'yield[s] excessive variation.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-071: John H. Blume & Stacey D. Neumann, "It's Like Deja Vu All Over Again": Williams v. Taylor, Wiggins v. Smith, Rompilla v. Beard and a (Partial) Return to the Guidelines Approach to the Effective Assistance of Counsel, 34 Am. J. Crim. L. 127 (2007)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 4 (Appel, J., concurring specially).

Authority type: secondary; as written: John H. Blume & Stacey D. Neumann, ... 34 Am. J. Crim. L. 127, 142 (2007); pincite: 142.

Cited for: Almost all representation found within Strickland's wide range

Quotes: ["[a]lmost all representation was found to be within Strickland's 'wide range of professionally competent assistance'"]

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Existence of the article (title, authors, 2007, American Journal of Criminal Law) confirmed through the Cornell Law faculty-publications record found by web search; the repository PDF was blocked by a bot challenge, so the article text, page 142, and the quoted words were not read.

Excerpt read: 

- https://scholarship.law.cornell.edu/facpub/38

### Second check: not required


## KUHSE-072: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 4 (Appel, J., concurring specially).

Authority type: case; as written: quoting Strickland, 466 U.S. at 690, 104 S. Ct. at 2066 (majority opinion); pincite: 690.

Cited for: Source of 'wide range of professionally competent assistance'

Quotes: ['wide range of professionally competent assistance']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-073: Martin C. Calhoun, How to Thread the Needle: Toward a Checklist-Based Standard for Evaluating Ineffective Assistance of Counsel Claims, 77 Geo. L.J. 413 (1988)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 16, footnote 4 (Appel, J., concurring specially).

Authority type: secondary; as written: Martin C. Calhoun, How to Thread the Needle ..., 77 Geo. L.J. 413, 455 (1988); pincite: 455.

Cited for: Critiquing Strickland as virtually insurmountable

Quotes: ['virtually insurmountable,', 'predictable and objective categorical approach']

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

No freely accessible copy or bibliographic record was found in one web search; text and quotations at 455 and 458 not read. Not a fabrication finding: Georgetown Law Journal back issues are not openly hosted.

Excerpt read: 


### Second check: not required


## KUHSE-074: Meredith J. Duncan, The (So-Called) Liability of Criminal Defense Attorneys: A System in Need of Reform, 2002 BYU L. Rev. 1

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF pages 16-17, footnote 4 (Appel, J., concurring specially).

Authority type: secondary; as written: Meredith J. Duncan, The (So-Called) Liability of Criminal Defense Attorneys ..., 2002 BYU L. Rev. 1, 27–28 (2002); pincite: 27-28.

Cited for: Strickland unworkable

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

One web search did not surface the article or a repository record; text and pages 27-28 not read. Not a fabrication finding.

Excerpt read: 


### Second check: not required


## KUHSE-075: Gary Feldon & Tara Beech, Unpacking the First Prong of the Strickland Standard: How to Identify Controlling Precedent and Determine Prevailing Professional Norms in Ineffective Assistance of Counsel Cases, 23 U. Fla. J.L. & Pub. Pol'y 1 (2012)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 17, footnote 4 (Appel, J., concurring specially).

Authority type: secondary; as written: Gary Feldon & Tara Beech, Unpacking the First Prong of the Strickland Standard ..., 23 U. Fla. J.L. & Pub. Pol'y 1, 9–15 (2012); pincite: 9-15.

Cited for: Post-Strickland confusion

Quotes: ['post-Strickland confusion']

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Existence confirmed through the UF Law scholarship repository record (vol. 23, iss. 1, art. 3) found by web search; text and pages 9-15 not read.

Excerpt read: 

- https://scholarship.law.ufl.edu/jlpp/vol23/iss1/3

### Second check: not required


## KUHSE-076: Elizabeth Gable & Tyler Green, Wiggins v. Smith: The Ineffective Assistance of Counsel Standard Applied Twenty Years After Strickland, 17 Geo. J. Legal Ethics 755 (2004)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 17, footnote 4 (Appel, J., concurring specially).

Authority type: secondary; as written: Elizabeth Gable & Tyler Green, Wiggins v. Smith ..., 17 Geo. J. Legal Ethics 755, 764–65 (2004); pincite: 764-65.

Cited for: Difficulty of Strickland

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Not searched beyond the Calhoun search; text and pages 764-65 not read. Not a fabrication finding.

Excerpt read: 


### Second check: not required


## KUHSE-077: Lovick v. Wil-Rich, 588 N.W.2d 688 (Iowa 1999)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 17 (slip op. at 17) (Appel, J., concurring specially).

Authority type: case; as written: Lovick v. Wil-Rich, 588 N.W.2d 688, 695 (Iowa 1999); pincite: 695.

Cited for: Instructions must give clear understanding

Quotes: ['a clear understanding of what they need to decide.']

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; the trial court has a duty to give the jury a clear understanding of what they need to decide (pin 695 not separately checked).

Excerpt read: A trial court has a duty to give the jury a clear understanding of what they need to decide.

- https://www.courtlistener.com/opinion/1987778/lovick-v-wil-rich/

### Second check: not required


## KUHSE-078: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 17 (slip op. at 17) (Appel, J., concurring specially).

Authority type: case; as written: Under Strickland; pincite: .

Cited for: Breach of duty not enough

Quotes: []

Context: Case name used as doctrine label.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-079: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 17 (slip op. at 17) (Appel, J., concurring specially).

Authority type: case; as written: the Strickland test; pincite: .

Cited for: Prejudice prong

Quotes: []

Context: Case name used as doctrine label.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-080: State v. Maxwell, 743 N.W.2d 185 (Iowa 2008)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 17 (slip op. at 17) (Appel, J., concurring specially).

Authority type: case; as written: State v. Maxwell, 743 N.W.2d 185, 196 (Iowa 2008); pincite: 196.

Cited for: Prejudice prong does not require more-likely-than-not

Quotes: ["does not mean a defendant must establish 'that counsel's deficient conduct more likely than not altered the outcome in the case.' A defendant need only show that the probability of a different result is 'sufficient to undermine confidence in the outcome.'"]

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener text; Maxwell block-quotes Bowman, 710 N.W.2d at 206, as Kuhse's concurrence quotes.

Excerpt read: test "does not mean a defendant must establish 'that counsel's deficient conduct more likely than not altered the outcome in the case.' A defendant need only show that the probability of a different result is 'sufficient to undermine confidence in the outcome.'" Id. at 206

- https://www.courtlistener.com/opinion/1575903/state-v-maxwell/

### Second check: not required


## KUHSE-081: Bowman v. State, 710 N.W.2d 200 (Iowa 2006)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 17 (slip op. at 17) (Appel, J., concurring specially).

Authority type: case; as written: quoting Bowman v. State, 710 N.W.2d 200, 206 (Iowa 2006); pincite: 206.

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority text; the quoted passage appears.

Excerpt read: does not mean a defendant must establish "that counsel's deficient conduct more likely than not altered the outcome in the case." A defendant need only show that the probability of a different result is "sufficient to undermine confidence in the outcome."

- https://www.courtlistener.com/opinion/1743023/bowman-v-state/

### Second check: not required


## KUHSE-082: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 17 (slip op. at 17) (Appel, J., concurring specially).

Authority type: case; as written: the Strickland test; pincite: .

Cited for: Difficulty of applying second prong

Quotes: []

Context: Case name used as doctrine label.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-083: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 18 (slip op. at 18) (Appel, J., concurring specially).

Authority type: case; as written: the so-called Strickland 'test'; pincite: .

Cited for: Impossible to apply in principled fashion

Quotes: []

Context: Case name used as doctrine label.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-084: Martin C. Calhoun, How to Thread the Needle: Toward a Checklist-Based Standard for Evaluating Ineffective Assistance of Counsel Claims, 77 Geo. L.J. 413 (1988)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 18, footnote 5 (Appel, J., concurring specially).

Authority type: secondary; as written: See, e.g., Calhoun, Threading the Needle, 77 Geo. L.J. at 458; pincite: 458.

Cited for: Statistics on Strickland outcomes

Quotes: []

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

No freely accessible copy or bibliographic record was found in one web search; text and quotations at 455 and 458 not read. Not a fabrication finding: Georgetown Law Journal back issues are not openly hosted.

Excerpt read: 


### Second check: not required


## KUHSE-085: Marcus Procter Henderson, Note, Truly Ineffective Assistance: A Comparison of Ineffective Assistance of Counsel in the United States of America and the United Kingdom, 13 Ind. Int'l & Comp. L. Rev. 317 (2002)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 18, footnote 5 (Appel, J., concurring specially).

Authority type: secondary; as written: Marcus Procter Henderson, Note, Truly Ineffective Assistance ..., 13 Ind. Int'l & Comp. L. Rev. 317, 331 (2002); pincite: 331.

Cited for: Inconsistent application

Quotes: ['would provide consistency in application,', 'inconsistent application, leading to a new level of arbitrariness']

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Not located in the session; text and page 331 not read. Not a fabrication finding.

Excerpt read: 


### Second check: not required


## KUHSE-086: Amy R. Murphy, Note, The Constitutional Failure of the Strickland Standard in Capital Cases Under the Eighth Amendment, 63 Law & Contemp. Probs. 179 (2000)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 18, footnote 5 (Appel, J., concurring specially).

Authority type: secondary; as written: Amy R. Murphy, Note, The Constitutional Failure of the Strickland Standard in Capital Cases Under the Eighth Amendment, 63-SUM Law & Contemp. Probs. 179, 199 (2000); pincite: 199.

Cited for: No pattern in outcomes

Quotes: ['there does not seem to be any pattern to what type of information will pass muster and what will not,', 'numerous examples of cases that failed the Strickland test, as well as examples of cases that survived it']

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Existence confirmed through the Duke Law scholarship repository record (63 Law & Contemp. Probs. 179-205, Summer 2000); the PDF download was blocked by a bot challenge, so page 199 and the quoted words were not read. Kuhse's '63-SUM' is a Westlaw-style issue designator.

Excerpt read: 

- https://scholarship.law.duke.edu/lcp/vol63/iss3/10

### Second check: not required


## KUHSE-087: Keith Cunningham-Parmeter, Dreaming of Effective Assistance: The Awakening of Cronic's Call to Presume Prejudice from Representational Absence, 76 Temp. L. Rev. 827 (2003)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 18, footnote 6 (Appel, J., concurring specially).

Authority type: secondary; as written: Keith Cunningham-Parmeter, Dreaming of Effective Assistance ..., 76 Temp. L. Rev. 827, 838–40 (2003); pincite: 838-40.

Cited for: Criticizing prejudice prong

Quotes: ['assum[es] that prejudice . . . will be detectable from the appellate record', 'unwarranted']

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Existence confirmed through the Lewis & Clark Law School repository record (76 Temp. L. Rev. 827-882 (2003)); text and pages 838-40 not read.

Excerpt read: 

- https://lawcommons.lclark.edu/faculty_articles/204

### Second check: not required


## KUHSE-088: Richard L. Gabriel, Comment, The Strickland Standard for Claims of Ineffective Assistance of Counsel: Emasculating the Sixth Amendment in the Guise of Due Process, 134 U. Pa. L. Rev. 1259 (1986)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 18, footnote 6 (Appel, J., concurring specially).

Authority type: secondary; as written: Richard L. Gabriel, The Strickland Standard for Claims of Ineffective Assistance of Counsel ..., 134 U. Pa. L. Rev. 1259, 1279–81 (1986); pincite: 1279-81.

Cited for: Impossibility of proving prejudice

Quotes: ['an outcome-determinative test', 'assumes one can determine what the result would have been had effective assistance of counsel been provided']

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

A web search returned a Penn Law repository listing (vol. 134, iss. 5, first page 1259, 1986), but the listed page returned 404 when fetched; text and pages 1279-81 not read.

Excerpt read: 

- https://scholarship.law.upenn.edu/penn_law_review/vol134/iss5/5

### Second check: not required


## KUHSE-089: Paul Marcus, The United States Supreme Court (Mostly) Gives Up Its Review Role with Ineffective Assistance of Counsel Cases, 100 Minn. L. Rev. 1745 (2016)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 18, footnote 6 (Appel, J., concurring specially).

Authority type: secondary; as written: Paul Marcus, The United States Supreme Court (Mostly) Gives Up Its Review Role with Ineffective Assistance of Counsel Cases, 100 Minn. L. Rev. 1745, 1752 (2016); pincite: 1752.

Cited for: Difficulty of proving the negative

Quotes: ['[H]ow does one prove the negative: how does one show what would have happened if there had been an engaged, thoughtful, and committed lawyer handling the trial? Proof of prejudice? Hardly likely to happen very often.']

Context: 

Fictional by design: False; 

### First check: UNABLE_TO_VERIFY

Existence confirmed through the University of Minnesota repository record (100 Minn. L. Rev. 1745-1768, 2016); the PDF download was blocked by a bot challenge, so page 1752 and the quoted words were not read.

Excerpt read: 

- https://scholarship.law.umn.edu/mlr/214

### Second check: not required


## KUHSE-090: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 19 (slip op. at 19) (Appel, J., concurring specially).

Authority type: case; as written: the second prong of Strickland; pincite: .

Cited for: Court of appeals found prong met

Quotes: []

Context: Case name used as doctrine label.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-091: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 19 (slip op. at 19) (Appel, J., concurring specially).

Authority type: case; as written: the amorphous Strickland test; pincite: .

Cited for: Applied as best as possible

Quotes: []

Context: Case name used as doctrine label.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## KUHSE-092: Strickland v. Washington, 466 U.S. 668 (1984)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/workdir/attachments/Kuhse.pdf; location: PDF page 21 (slip op. at 21) (Appel, J., concurring specially).

Authority type: case; as written: the amorphous Strickland standard; pincite: .

Cited for: Applied; no substantial probability of different verdict

Quotes: []

Context: Case name used as doctrine label.

Fictional by design: False; 

### First check: VERIFIED

Read CourtListener majority and Marshall dissent. The two-component test and 'not functioning as the "counsel"' language (687), 'reasonable considering all the circumstances' (688), 'wide range of professionally competent assistance' (690), the reasonable-probability definition (694), and Justice Marshall's 'so malleable ... no grip at all or will yield excessive variation' (707, dissenting) all appear as quoted.

Excerpt read: This requires showing that counsel made errors so serious that counsel was not functioning as the "counsel" guaranteed the defendant by the Sixth Amendment. ... the performance inquiry must be whether counsel's assistance was reasonable considering all the circumstances. ... A reasonable probability is a probability sufficient to undermine confidence in the outcome. [Marshall, J., dissenting:] it is so malleable that, in practice, it will either have no grip at all or will yield excessive variation

- https://www.courtlistener.com/opinion/111170/strickland-v-washington/

### Second check: not required


## PLEA-001: Iowa Code § 708.6 (2020)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 1 (Count XX petition), charge line.

Authority type: statute; as written: Iowa Code §(s) 708.6; pincite: .

Cited for: Charge: intimidation with a dangerous weapon

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 text (defines intimidation with a dangerous weapon as shooting into an occupied vehicle with intent to injure or provoke fear). The supplied file is the 'Iowa Code 2026' print; compared word-for-word with the official 2020 edition, the text is identical apart from print-date lines and 'Referred to in' annotations. Whether § 708.6 is a 'forcible felony' under § 702.11 is not stated in either text.

Excerpt read: 1. A person commits a class "C" felony when the person, with the intent to injure or provoke fear or anger in another, shoots, throws, launches, or discharges a dangerous weapon at, into, or in a building, vehicle, ... occupied by another person

- https://www.legis.iowa.gov/docs/code/2020/708.6.pdf

### Second check: not required


## PLEA-002: Iowa Code § 725.1(2)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 2 (Count XX petition), surcharge lines (struck through on form).

Authority type: statute; as written: § 725.1(2); pincite: .

Cited for: Offenses triggering $1,000 human trafficking surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (§ 725.1 prostitution) and § 911.2A, which imposes the $1,000 human trafficking victim surcharge for violations of § 725.1(2), 710A.2, 725.2, or 725.3, matching the plea form's (struck) line.

Excerpt read: 911.2A ... shall assess a human trafficking victim surcharge of one thousand dollars if an adjudication of guilt or a deferred judgment has been entered for a criminal violation of section 725.1, subsection 2, or section 710A.2, 725.2, or 725.3.

- https://www.legis.iowa.gov/docs/code/2020/725.1.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2A.pdf

### Second check: not required


## PLEA-003: Iowa Code § 710A.2

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 2 (Count XX petition), surcharge lines (struck through on form).

Authority type: statute; as written: 710A.2; pincite: .

Cited for: Offenses triggering $1,000 human trafficking surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (human trafficking); listed in § 911.2A as a surcharge offense, consistent with the plea form.

Excerpt read: 710A.2 Human trafficking. 1. A person who knowingly engages in human trafficking is guilty of a class "D" felony

- https://www.legis.iowa.gov/docs/code/2020/710A.2.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2A.pdf

### Second check: not required


## PLEA-004: Iowa Code § 725.2

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 2 (Count XX petition), surcharge lines (struck through on form).

Authority type: statute; as written: 725.2; pincite: .

Cited for: Offenses triggering $1,000 human trafficking surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (pimping); listed in § 911.2A, consistent with the plea form.

Excerpt read: 725.2 Pimping. 1. A person who solicits a patron for a prostitute ...

- https://www.legis.iowa.gov/docs/code/2020/725.2.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2A.pdf

### Second check: not required


## PLEA-005: Iowa Code § 725.3

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 2 (Count XX petition), surcharge lines (struck through on form).

Authority type: statute; as written: 725.3; pincite: .

Cited for: Offenses triggering $1,000 human trafficking surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (pandering); listed in § 911.2A, consistent with the plea form.

Excerpt read: 725.3 Pandering. 1. A person who persuades, arranges, coerces, or otherwise causes another, not a minor, to become a prostitute

- https://www.legis.iowa.gov/docs/code/2020/725.3.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2A.pdf

### Second check: not required


## PLEA-006: Iowa Code § 708.2A (plea form surcharge line)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 2 (Count XX petition), surcharge lines (struck through on form).

Authority type: statute; as written: § 708.2A; pincite: .

Cited for: Offenses triggering domestic/sex abuse surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 § 708.2A and § 911.2B; § 911.2B imposes the domestic abuse/sexual abuse/stalking surcharge for violations of § 708.2A, 708.11, 710A.2, or chapter 709. The form's offense list matches; the form states $90 while the 2020 Code (as of January 2020) states $100 -- a possible later 2020 amendment was not checked, and the line is struck through on the form.

Excerpt read: 911.2B ... shall assess a domestic abuse assault, sexual abuse, stalking, and human trafficking victim surcharge of one hundred dollars if an adjudication of guilt or a deferred judgment has been entered for a violation of section 708.2A, 708.11, or 710A.2, or chapter 709.

- https://www.legis.iowa.gov/docs/code/2020/708.2A.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2B.pdf

### Second check: not required


## PLEA-007: Iowa Code § 708.11

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 2 (Count XX petition), surcharge lines (struck through on form).

Authority type: statute; as written: 708.11; pincite: .

Cited for: Offenses triggering domestic/sex abuse surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (stalking); listed in § 911.2B, consistent with the plea form (see § 708.2A entry on the surcharge amount).

Excerpt read: 708.11 Stalking.

- https://www.legis.iowa.gov/docs/code/2020/708.11.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2B.pdf

### Second check: not required


## PLEA-008: Iowa Code ch. 709

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 2 (Count XX petition), surcharge lines (struck through on form).

Authority type: statute; as written: chapter 709; pincite: .

Cited for: Offenses triggering domestic/sex abuse surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 chapter heading (sexual abuse); listed in § 911.2B, consistent with the plea form.

Excerpt read: CHAPTER 709 SEXUAL ABUSE

- https://www.legis.iowa.gov/docs/code/2020/709.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2B.pdf

### Second check: not required


## PLEA-009: Iowa Code ch. 249A

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 2 (Count XX petition), Category B restitution paragraph.

Authority type: statute; as written: chapter 249A; pincite: .

Cited for: Restitution to medical assistance program

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 chapter heading; chapter 249A is Medical Assistance, matching the plea form's reference to restitution to the medical assistance program.

Excerpt read: CHAPTER 249A MEDICAL ASSISTANCE

- https://www.legis.iowa.gov/docs/code/2020/249A.pdf

### Second check: not required


## PLEA-010: Iowa Code § 811.1(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 2 (Count XX petition), bond checkbox (unchecked).

Authority type: statute; as written: Iowa Code § 811.1(1); pincite: .

Cited for: Not eligible for bond after plea

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; defendants awaiting judgment after a plea of guilty to a forcible felony are not bailable, matching the plea form's bond line.

Excerpt read: the following defendants shall not be admitted to bail: 1. A defendant awaiting judgment of conviction and sentencing following either a plea or verdict of guilty of a class "A" felony; forcible felony as defined in section 702.11; ...

- https://www.legis.iowa.gov/docs/code/2020/811.1.pdf

### Second check: not required


## PLEA-011: Iowa Code § 725.1(2)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 5 (Count VIII petition), surcharge lines (struck through on form).

Authority type: statute; as written: § 725.1(2); pincite: .

Cited for: Offenses triggering $1,000 human trafficking surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (§ 725.1 prostitution) and § 911.2A, which imposes the $1,000 human trafficking victim surcharge for violations of § 725.1(2), 710A.2, 725.2, or 725.3, matching the plea form's (struck) line.

Excerpt read: 911.2A ... shall assess a human trafficking victim surcharge of one thousand dollars if an adjudication of guilt or a deferred judgment has been entered for a criminal violation of section 725.1, subsection 2, or section 710A.2, 725.2, or 725.3.

- https://www.legis.iowa.gov/docs/code/2020/725.1.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2A.pdf

### Second check: not required


## PLEA-012: Iowa Code § 710A.2

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 5 (Count VIII petition), surcharge lines (struck through on form).

Authority type: statute; as written: 710A.2; pincite: .

Cited for: Offenses triggering $1,000 human trafficking surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (human trafficking); listed in § 911.2A as a surcharge offense, consistent with the plea form.

Excerpt read: 710A.2 Human trafficking. 1. A person who knowingly engages in human trafficking is guilty of a class "D" felony

- https://www.legis.iowa.gov/docs/code/2020/710A.2.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2A.pdf

### Second check: not required


## PLEA-013: Iowa Code § 725.2

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 5 (Count VIII petition), surcharge lines (struck through on form).

Authority type: statute; as written: 725.2; pincite: .

Cited for: Offenses triggering $1,000 human trafficking surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (pimping); listed in § 911.2A, consistent with the plea form.

Excerpt read: 725.2 Pimping. 1. A person who solicits a patron for a prostitute ...

- https://www.legis.iowa.gov/docs/code/2020/725.2.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2A.pdf

### Second check: not required


## PLEA-014: Iowa Code § 725.3

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 5 (Count VIII petition), surcharge lines (struck through on form).

Authority type: statute; as written: 725.3; pincite: .

Cited for: Offenses triggering $1,000 human trafficking surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (pandering); listed in § 911.2A, consistent with the plea form.

Excerpt read: 725.3 Pandering. 1. A person who persuades, arranges, coerces, or otherwise causes another, not a minor, to become a prostitute

- https://www.legis.iowa.gov/docs/code/2020/725.3.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2A.pdf

### Second check: not required


## PLEA-015: Iowa Code § 708.2A (plea form surcharge line)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 5 (Count VIII petition), surcharge lines (struck through on form).

Authority type: statute; as written: § 708.2A; pincite: .

Cited for: Offenses triggering domestic/sex abuse surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 § 708.2A and § 911.2B; § 911.2B imposes the domestic abuse/sexual abuse/stalking surcharge for violations of § 708.2A, 708.11, 710A.2, or chapter 709. The form's offense list matches; the form states $90 while the 2020 Code (as of January 2020) states $100 -- a possible later 2020 amendment was not checked, and the line is struck through on the form.

Excerpt read: 911.2B ... shall assess a domestic abuse assault, sexual abuse, stalking, and human trafficking victim surcharge of one hundred dollars if an adjudication of guilt or a deferred judgment has been entered for a violation of section 708.2A, 708.11, or 710A.2, or chapter 709.

- https://www.legis.iowa.gov/docs/code/2020/708.2A.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2B.pdf

### Second check: not required


## PLEA-016: Iowa Code § 708.11

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 5 (Count VIII petition), surcharge lines (struck through on form).

Authority type: statute; as written: 708.11; pincite: .

Cited for: Offenses triggering domestic/sex abuse surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text (stalking); listed in § 911.2B, consistent with the plea form (see § 708.2A entry on the surcharge amount).

Excerpt read: 708.11 Stalking.

- https://www.legis.iowa.gov/docs/code/2020/708.11.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2B.pdf

### Second check: not required


## PLEA-017: Iowa Code ch. 709

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 5 (Count VIII petition), surcharge lines (struck through on form).

Authority type: statute; as written: chapter 709; pincite: .

Cited for: Offenses triggering domestic/sex abuse surcharge (line struck)

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 chapter heading (sexual abuse); listed in § 911.2B, consistent with the plea form.

Excerpt read: CHAPTER 709 SEXUAL ABUSE

- https://www.legis.iowa.gov/docs/code/2020/709.pdf
- https://www.legis.iowa.gov/docs/code/2020/911.2B.pdf

### Second check: not required


## PLEA-018: Iowa Code ch. 249A

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 5 (Count VIII petition), Category B restitution paragraph.

Authority type: statute; as written: chapter 249A; pincite: .

Cited for: Restitution to medical assistance program

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 chapter heading; chapter 249A is Medical Assistance, matching the plea form's reference to restitution to the medical assistance program.

Excerpt read: CHAPTER 249A MEDICAL ASSISTANCE

- https://www.legis.iowa.gov/docs/code/2020/249A.pdf

### Second check: not required


## PLEA-019: Iowa Code § 811.1(1)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 5 (Count VIII petition), bond checkbox (unchecked).

Authority type: statute; as written: Iowa Code § 811.1(1); pincite: .

Cited for: Not eligible for bond after plea

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; defendants awaiting judgment after a plea of guilty to a forcible felony are not bailable, matching the plea form's bond line.

Excerpt read: the following defendants shall not be admitted to bail: 1. A defendant awaiting judgment of conviction and sentencing following either a plea or verdict of guilty of a class "A" felony; forcible felony as defined in section 702.11; ...

- https://www.legis.iowa.gov/docs/code/2020/811.1.pdf

### Second check: not required


## PLEA-020: Iowa Code § 706.1

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 4 (Count VIII petition), charge line.

Authority type: statute; as written: Iowa Code §(s) 706.1 [and 706.3]; pincite: .

Cited for: Charge: conspiracy to commit a forcible felony

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read the official 2020 text. The supplied file is the 'Iowa Code 2026' print; compared word-for-word with the official 2020 edition, the text is identical apart from print-date lines and 'Referred to in' annotations.

Excerpt read: 706.1 Conspiracy. 1. A person commits conspiracy with another if, with the intent to promote or facilitate the commission of a crime which is an aggravated misdemeanor or felony, the person does either of the following: a. Agrees with another that they or one or more of them will engage in conduct constituting the crime ...

- https://www.legis.iowa.gov/docs/code/2020/706.1.pdf

### Second check: not required


## PLEA-021: Iowa Code § 706.3

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/Patton State Plea.pdf; location: PDF page 4 (Count VIII petition), charge line.

Authority type: statute; as written: [Iowa Code §(s) 706.1 and] 706.3; pincite: .

Cited for: Same

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Read official 2020 text; conspiracy to commit a forcible felony is a class C felony, consistent with the plea form's charge and the 10-year maximum it lists.

Excerpt read: 1. A person who commits a conspiracy to commit a forcible felony is guilty of a class "C" felony.

- https://www.legis.iowa.gov/docs/code/2020/706.3.pdf

### Second check: not required


## S702-11-001: Iowa Code § 708.4(2)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/702.11.pdf; location: PDF page 1, subsection 2.

Authority type: statute; as written: section 708.4, subsection 2 [2(a)]; pincite: .

Cited for: Offense excluded from the forcible-felony definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: 2. A class "D" felony, if the person causes bodily injury to another.

- https://www.legis.iowa.gov/docs/code/2026/708.4.pdf

### Second check: not required


## S702-11-002: Iowa Code § 709.4(1)(b)(2)(d)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/702.11.pdf; location: PDF page 1, subsection 2.

Authority type: statute; as written: section 709.4, subsection 1, paragraph "b", subparagraph (2), subparagraph division (d) [2(c)]; pincite: .

Cited for: Offense excluded from the forcible-felony definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description. (2026 numbering; the 2020 edition used subparagraph (3)).

Excerpt read: b. The act is between persons who are not at the time cohabiting as husband and wife and if any of the following are true: ... (2) The other person is fourteen or fifteen years of age and any of the following are true: ... (d) The person is four or more years older than the other person.

- https://www.legis.iowa.gov/docs/code/2026/709.4.pdf

### Second check: not required


## S702-11-003: Iowa Code § 709.15

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/702.11.pdf; location: PDF page 1, subsection 2.

Authority type: statute; as written: section 709.15 [2(d)]; pincite: .

Cited for: Offense excluded from the forcible-felony definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: 709.15 Sexual exploitation by counselor, therapist, school employee, or adult providing training or instruction.

- https://www.legis.iowa.gov/docs/code/2026/709.15.pdf

### Second check: not required


## S702-11-004: Iowa Code § 726.6(7)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/702.11.pdf; location: PDF page 1, subsection 2.

Authority type: statute; as written: section 726.6, subsection 7 [2(e)]; pincite: .

Cited for: Offense excluded from the forcible-felony definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description. (2026 numbering; 2020 used subsection 6).

Excerpt read: 7. A person who commits child endangerment resulting in bodily injury to a child or minor ...

- https://www.legis.iowa.gov/docs/code/2026/726.6.pdf

### Second check: not required


## S702-11-005: Iowa Code § 708.2(5)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/702.11.pdf; location: PDF page 1, subsection 2.

Authority type: statute; as written: section 708.2, subsection 5 [2(f)]; pincite: .

Cited for: Offense excluded from the forcible-felony definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description. (2026 numbering; 2020 used subsection 4).

Excerpt read: 5. A person who commits an assault, as defined in section 708.1, without the intent to inflict serious injury, but who causes serious injury, is guilty of a class "D" felony.

- https://www.legis.iowa.gov/docs/code/2026/708.2.pdf

### Second check: not required


## S702-11-006: Iowa Code § 708.2A(5)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/702.11.pdf; location: PDF page 1, subsection 2.

Authority type: statute; as written: section 708.2A, subsection 5 [2(g)]; pincite: .

Cited for: Offense excluded from the forcible-felony definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: 5. For a domestic abuse assault committed by knowingly impeding the normal breathing or circulation of the blood of another by applying pressure to the throat or neck

- https://www.legis.iowa.gov/docs/code/2026/708.2A.pdf

### Second check: not required


## S702-11-007: Iowa Code § 708.12(3)(f)

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/702.11.pdf; location: PDF page 1, subsection 2.

Authority type: statute; as written: section 708.12, subsection 3, paragraph "f" [2(h)]; pincite: .

Cited for: Offense excluded from the forcible-felony definition

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: f. If a violation of paragraph "a" occurs and the person knowingly or intentionally causes serious injury to the officer the person is guilty of a class "D" felony.

- https://www.legis.iowa.gov/docs/code/2026/708.12.pdf

### Second check: not required


## S704-001: Iowa Code § 702.8

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/704.pdf; location: PDF page 3, § 704.9.

Authority type: statute; as written: section 702.8; pincite: .

Cited for: Definition of death

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: 702.8 Death. "Death" means the condition determined by the following standard

- https://www.legis.iowa.gov/docs/code/2026/702.8.pdf

### Second check: not required


## S704-002: Iowa Code § 705.1

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/704.pdf; location: PDF page 4, § 704.11.

Authority type: statute; as written: section 705.1; pincite: .

Cited for: Crime of solicitation

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: 705.1 Solicitation. 1. A person solicits another person to commit a felony or aggravated misdemeanor when ...

- https://www.legis.iowa.gov/docs/code/2026/705.1.pdf

### Second check: not required


## S704-003: Iowa Code § 804.8

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/704.pdf; location: PDF page 4, § 704.12.

Authority type: statute; as written: sections 804.8; pincite: .

Cited for: Force permitted in making an arrest

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: 804.8 Use of force by peace officer making an arrest.

- https://www.legis.iowa.gov/docs/code/2026/804.8.pdf

### Second check: not required


## S704-004: Iowa Code § 804.10

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/704.pdf; location: PDF page 4, § 704.12.

Authority type: statute; as written: section 804.10; pincite: .

Cited for: Force permitted in making an arrest

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: 804.10 Use of force in arrest by private person.

- https://www.legis.iowa.gov/docs/code/2026/804.10.pdf

### Second check: not required


## S704-005: Iowa Code § 804.13

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/704.pdf; location: PDF page 4, § 704.12.

Authority type: statute; as written: section 804.13; pincite: .

Cited for: Force permitted in making an arrest

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: 804.13 Use of force in preventing an escape.

- https://www.legis.iowa.gov/docs/code/2026/804.13.pdf

### Second check: not required


## S704-006: Iowa Code § 804.15

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/704.pdf; location: PDF page 4, § 704.12.

Authority type: statute; as written: section 804.15; pincite: .

Cited for: Force permitted in making an arrest

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: 804.15 Breaking and entering premises -- demand to enter.

- https://www.legis.iowa.gov/docs/code/2026/804.15.pdf

### Second check: not required


## S704-007: Iowa Code § 704.4

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/704.pdf; location: PDF page 4, § 704.13.

Authority type: statute; as written: section 704.4; pincite: .

Cited for: Immunity for justified defense of property

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Internal cross-reference within the supplied chapter 704 print; read § 704.4 in the same supplied file (identical to the official 2020 text). It concerns defense of property, matching § 704.13's reference.

Excerpt read: 704.4 Defense of property. A person is justified in the use of reasonable force to prevent or terminate criminal interference with the person's possession or other right in property.

- https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/704.pdf

### Second check: not required


## S707-11-001: Iowa Code ch. 692A

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/707.11.pdf; location: PDF page 1, § 707.11(4).

Authority type: statute; as written: chapter 692A; pincite: .

Cited for: Sex offender registration

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description. Chapter 692A is the sex offender registry (heading read in § 692A.126 and § 692A.102 prints).

Excerpt read: SEX OFFENDER REGISTRY, §692A.126

- https://www.legis.iowa.gov/docs/code/2026/692A.126.pdf

### Second check: not required


## S707-11-002: Iowa Code § 692A.126

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/707.11.pdf; location: PDF page 1, § 707.11(4).

Authority type: statute; as written: section 692A.126; pincite: .

Cited for: Sexually motivated offense determination

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: 692A.126 Sexually motivated offense -- determination.

- https://www.legis.iowa.gov/docs/code/2026/692A.126.pdf

### Second check: not required


## S707-11-003: Iowa Code § 801.4

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/707.11.pdf; location: PDF page 1, § 707.11(5)(a).

Authority type: statute; as written: section 801.4; pincite: .

Cited for: Definition of peace officer

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description. § 801.4 defines 'peace officers'.

Excerpt read: 801.4 Definitions. ... "Peace officers", sometimes designated "law enforcement officers"

- https://www.legis.iowa.gov/docs/code/2026/801.4.pdf

### Second check: not required


## S707-11-004: Iowa Code § 903A.2

Document: tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/workdir/attachments/707.11.pdf; location: PDF page 1, § 707.11(5)(b).

Authority type: statute; as written: section 903A.2; pincite: .

Cited for: Sentence category / earned time

Quotes: []

Context: 

Fictional by design: False; 

### First check: VERIFIED

Cross-reference in the operative text of the supplied 2026 print; read the referenced 2026 section on the Iowa Legislature site and it matches the description.

Excerpt read: 903A.2 Earned time. 1. Each inmate committed to the custody of the director of the department of corrections ...

- https://www.legis.iowa.gov/docs/code/2026/903A.2.pdf

### Second check: not required
