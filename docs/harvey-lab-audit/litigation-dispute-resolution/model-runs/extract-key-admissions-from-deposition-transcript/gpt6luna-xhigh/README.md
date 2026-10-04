# GPT-6 Luna (xhigh): Extract Key Admissions from Deposition Transcript — Admission Summary Memorandum

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/extract-key-admissions-from-deposition-transcript/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 40 of 46 criteria; GPT-5.5 passed 44 of 46 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [admission-summary-memo.docx](output/admission-summary-memo.docx) ([read as Markdown](output/admission-summary-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | ISSUE_001: Identifies Yoon's first contact with PAG was June 22, 2024 dinner | Pass | Pass |
| [C-002](#c-002) | ISSUE_001: Flags contradiction with Interrogatory No. 4 | Pass | Pass |
| [C-003](#c-003) | ISSUE_001: Notes Yoon was still CTO at time of first PAG contact | **Fail** | Pass |
| [C-004](#c-004) | ISSUE_002: Identifies Yoon's admission of USB file transfer | Pass | Pass |
| [C-005](#c-005) | ISSUE_002: Flags contradiction with Interrogatory No. 7 | Pass | Pass |
| [C-006](#c-006) | ISSUE_002: Notes Yoon could not identify the 3,847 files | Pass | Pass |
| [C-007](#c-007) | ISSUE_003: Identifies Yoon's admission of emailing Blue Book | Pass | Pass |
| [C-008](#c-008) | ISSUE_003: Flags Yoon's shift from denial to qualified admission on Blue Book email | Pass | Pass |
| [C-009](#c-009) | ISSUE_003: Cross-references forensic report evidence | Pass | Pass |
| [C-010](#c-010) | ISSUE_004a: Identifies Yoon's admission of attending MillEdge Pro technical architecture review | Pass | Pass |
| [C-011](#c-011) | ISSUE_004b: Identifies Yoon's admission of reviewing MillEdge Pro codebase | Pass | Pass |
| [C-012](#c-012) | ISSUE_004: Flags contradiction with Interrogatory No. 12 | Pass | Pass |
| [C-013](#c-013) | ISSUE_005: Identifies Yoon's misstatement of non-compete radius | Pass | Pass |
| [C-014](#c-014) | ISSUE_005: Notes strategic significance of radius discrepancy | **Fail** | Pass |
| [C-015](#c-015) | ISSUE_006: Identifies suspicious spike in patent file access | Pass | Pass |
| [C-016](#c-016) | ISSUE_006: Notes Yoon's failure to provide business reason for patent access spike | Pass | Pass |
| [C-017](#c-017) | ISSUE_007: Identifies Yoon told Adwell about non-compete before starting at PAG | Pass | Pass |
| [C-018](#c-018) | ISSUE_007: Connects Adwell's awareness to tortious interference claim | **Fail** | **Fail** |
| [C-019](#c-019) | ISSUE_008: Identifies inconsistency re Separation Acknowledgment and USB drive | Pass | Pass |
| [C-020](#c-020) | ISSUE_008: Notes Yoon's 'forgot about the USB drive' explanation | Pass | Pass |
| [C-021](#c-021) | ISSUE_009: Identifies Yoon's use of 'harmonic frequency matching' terminology when describing MillEdge Pro | Pass | Pass |
| [C-022](#c-022) | ISSUE_009: Notes Yoon could not cite published source for 'harmonic frequency matching' terminology | Pass | Pass |
| [C-023](#c-023) | ISSUE_009: Connects terminology to potential trade secret migration | Pass | Pass |
| [C-024](#c-024) | ISSUE_010: Identifies factory reset of personal iPhone as spoliation issue | Pass | Pass |
| [C-025](#c-025) | ISSUE_010: Notes litigation was reasonably anticipated before reset | Pass | Pass |
| [C-026](#c-026) | ISSUE_010: Mentions adverse inference or sanctions possibility | Pass | Pass |
| [C-027](#c-027) | ISSUE_011: Notes enforceability question on non-compete scope | Pass | Pass |
| [C-028](#c-028) | ISSUE_011: References Michigan non-compete law or blue-pencil doctrine | **Fail** | Pass |
| [C-029](#c-029) | Assesses significance for trade secret misappropriation claim | Pass | Pass |
| [C-030](#c-030) | Assesses significance for breach of non-compete claim | Pass | Pass |
| [C-031](#c-031) | Assesses significance for tortious interference claim | **Fail** | **Fail** |
| [C-032](#c-032) | Summary table of admissions with cross-references | **Fail** | Pass |
| [C-033](#c-033) | Recommends motion to compel supplemental interrogatory answers | Pass | Pass |
| [C-034](#c-034) | Recommends spoliation sanctions motion or related action | Pass | Pass |
| [C-035](#c-035) | Recommends additional discovery or subpoenas | Pass | Pass |
| [C-036](#c-036) | Correct case name | Pass | Pass |
| [C-037](#c-037) | Correct case number | Pass | Pass |
| [C-038](#c-038) | Correct court | Pass | Pass |
| [C-039](#c-039) | Identifies Interrogatory No. 4 contradiction (first contact with PAG) | Pass | Pass |
| [C-040](#c-040) | Identifies Interrogatory No. 7 contradiction (removal of documents) | Pass | Pass |
| [C-041](#c-041) | Identifies Interrogatory No. 12 contradiction (involvement in CNC products at PAG) | Pass | Pass |
| [C-042](#c-042) | References Employment Agreement Section 7(a) for non-compete terms | Pass | Pass |
| [C-043](#c-043) | References forensic report for USB and email evidence | Pass | Pass |
| [C-044](#c-044) | References Separation Acknowledgment document | Pass | Pass |
| [C-045](#c-045) | References cease-and-desist letter for spoliation timeline | Pass | Pass |
| [C-046](#c-046) | Identifies USB drive details correctly | Pass | Pass |

## Judge reasoning

### C-001

ISSUE_001: Identifies Yoon's first contact with PAG was June 22, 2024 dinner ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L19))

- **Sonnet 4.6: Pass.** The memo explicitly mentions the June 22 dinner with Adwell in Section 2C: 'he testified the June 22 dinner followed a June 8--9 industry event, Adwell described a CNC-optimization venture, and they discussed his non-compete.' This identifies the June 22, 2024 dinner with Adwell and notes that they discussed a CNC-optimization venture, satisfying the criterion.
- **GPT-5.5: Pass.** The memo expressly states that Yoon testified about a June 22 dinner with Adwell, and that Adwell described a CNC-optimization venture. This identifies the deposition admission and the relevant discussion topic.

### C-002

ISSUE_001: Flags contradiction with Interrogatory No. 4 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L27))

- **Sonnet 4.6: Pass.** Section 2C of the memo explicitly addresses the contradiction between Yoon's interrogatory answers and his deposition testimony regarding PAG contact timing. It specifically references 'Interrogatory 4' which 'says first contact with Adwell occurred in late August, after resignation,' and contrasts this with testimony about the June 22 dinner following a June 8-9 industry event where Adwell described a CNC-optimization venture. The memo also cites 'Interrogatory Answers Nos. 3--4, 11' in the supporting citations. This directly satisfies the criterion of flagging the contradiction between the June 22, 2024 contact admission and Interrogatory No. 4's 'late August' claim.
- **GPT-5.5: Pass.** The memo expressly flags a contradiction: it states that Interrogatory No. 4 says Yoon's first contact with Adwell occurred in late August after resignation, while his deposition testimony described a June 22 dinner/contact with Adwell. This directly satisfies the criterion.

### C-003

ISSUE_001: Notes Yoon was still CTO at time of first PAG contact ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L35))

- **Sonnet 4.6: Fail.** The memo mentions the June 22 dinner and the August 16 resignation date (implied by 'August 20 offer came four days after resignation' and 'August 14 wrapping things up email'), and notes the June 8-9 industry event and June 22 dinner in Section 2C. However, the memo does not explicitly connect these facts to state that Yoon was still employed as CMS CTO at the time of the June 22 dinner. The criterion requires the memo to note that the June 22 contact occurred nearly two months before the August 16 resignation, meaning Yoon was still CTO when he first contacted PAG. While the timeline is present in the memo, the explicit connection that Yoon was still employed as CTO during the June 22 contact is not made. The memo discusses the contradiction between interrogatory answers and actual contact dates, but does not specifically highlight that Yoon was still CTO at the time of first PAG contact as a notable fact.
- **GPT-5.5: Pass.** The memo identifies the June 22 dinner/contact with Adwell and contrasts it with Yoon’s interrogatory claim of first contact after resignation. It also notes the August 20 offer was four days after resignation and that earlier communications show the process was underway before resignation. Although it does not use the exact phrase “still CTO,” it sufficiently connects the June 22 PAG/Adwell contact to the period before Yoon’s August 16 resignation while he remained employed at CMS.

### C-004

ISSUE_002: Identifies Yoon's admission of USB file transfer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L43))

- **Sonnet 4.6: Pass.** The memo clearly identifies Yoon's admission regarding the USB file transfer in Section 1 under 'USB transfer.' It states he 'acknowledged that he may have connected his USB drive and transferred files' and that 'he copied a folder/set of folders from his work area, did not review each file.' The forensic analysis is cited (Forensic Report §§5.1, 4.2) showing 3,847 files copied on August 10, 2024. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly states that Yoon acknowledged he may have connected his USB drive and transferred files, and ties the forensic report to 3,847 files copied to a SanDisk USB drive on August 10, 2024.

### C-005

ISSUE_002: Flags contradiction with Interrogatory No. 7 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L51))

- **Sonnet 4.6: Pass.** The memo explicitly references Interrogatory No. 7 in Section 2A, stating: 'Interrogatory 7 says he "did not remove or copy any confidential or proprietary documents"' and identifies this as contradicting the forensic USB evidence and his deposition admission that he copied folders to a USB drive. This directly satisfies the criterion of flagging the contradiction between the USB transfer admission and Interrogatory No. 7.
- **GPT-5.5: Pass.** The memo expressly states that Interrogatory 7 says Yoon “did not remove or copy any confidential or proprietary documents” and identifies that answer as conflicting with the forensic USB event and his deposition admission that he copied folders/files to a likely personal USB drive.

### C-006

ISSUE_002: Notes Yoon could not identify the 3,847 files ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L59))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 1 (USB transfer bullet): 'he copied a folder/set of folders from his work area, did not review each file, could not name one file, and could not identify which files were personal.' This directly addresses both that Yoon did not review each file individually before copying and that he could not identify any of the transferred files. The criterion is satisfied.
- **GPT-5.5: Pass.** The memo expressly states that Yoon copied folders without reviewing each file, could not name one file, and could not identify which files were personal; it also reiterates he could not identify any transferred file and did not inspect the batch.

### C-007

ISSUE_003: Identifies Yoon's admission of emailing Blue Book ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L67))

- **Sonnet 4.6: Pass.** The memo clearly identifies Yoon's Blue Book email admission in Section 1 ('Blue Book transmission') and Section 2B. It notes he initially said he did not recall the email, then admitted he 'may have forwarded it inadvertently.' It identifies his CMS sender account and personal Gmail recipient, the August 12 date, and the forensic confirmation of an exact hash-matched copy. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly addresses the Blue Book email: it states Yoon recognized his CMS sender account and personal Gmail recipient, initially did not recall the email, then said he may have forwarded it inadvertently, and notes the restricted pricing matrix was sent on August 12. This satisfies the required identification of the admission/concession.

### C-008

ISSUE_003: Flags Yoon's shift from denial to qualified admission on Blue Book email ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L75))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Yoon's shift in testimony regarding the Blue Book email in Section 1 (Blue Book transmission) and Section 2B. In Section 1, it states: 'after first saying he did not recall the email, he said he may have forwarded it inadvertently while cleaning his inbox and was not scrutinizing attachments.' Section 2B further elaborates: 'Yoon initially did not recall sending the email, then described a possible inadvertent forward.' This directly captures both the initial denial/non-recollection and the subsequent qualified admission with the 'inadvertent' explanation, satisfying the criterion.
- **GPT-5.5: Pass.** The memo expressly notes Yoon first said he did not recall/denied the Blue Book email and later gave a qualified admission that he may have forwarded it inadvertently while cleaning his inbox, including highlighting the change from 'did not' to 'may have.'

### C-009

ISSUE_003: Cross-references forensic report evidence ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L83))

- **Sonnet 4.6: Pass.** The memo cross-references the Blue Book testimony against the Ridgepoint Digital Forensics Report multiple times. In Section 1 (Blue Book transmission), it states: 'The forensic report says the attachment was an exact, hash-matched copy of CMS's restricted customer pricing matrix, sent August 12 with no subject/body.' In Section 2B, it references 'Forensics identifies the confidential pricing workbook as an exact copy emailed to his personal account.' The memo also cites 'Forensic Report §5.2' and 'Vol. I at 131--37' (Exhibit 15 examination). Additionally, Section 5 notes a timestamp discrepancy between the Volume I examination of Exhibit 15 (11:47 a.m.) and the forensic report (14:22:17 EDT), and recommends reconciling via 'native Exchange transport records, headers, and source exhibit.' The memo references sender/recipient addresses (CMS sender account and personal Gmail), attachment metadata (hash-matched copy, exact copy), and the forensic report corroboration. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly cross-references Yoon’s Blue Book testimony with the Ridgepoint Forensic Report, stating that the report identified an exact hash-matched attachment sent from his CMS account to his personal Gmail with no subject/body and citing Forensic Report §5.2. It also discusses the timestamp discrepancy and need to review native Exchange headers. Although it does not spell out every metadata field or exact filename, it does reference forensic/documentary evidence corroborating the Blue Book email.

### C-010

ISSUE_004a: Identifies Yoon's admission of attending MillEdge Pro technical architecture review ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L91))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 1 (Most material admissions) under 'PAG timing and role': 'At PAG he attended a September 4 MillEdge Pro architecture review, made suggestions, had 11 September commits...' This directly identifies Yoon's admission of attending the MillEdge Pro technical architecture review in his first week at PAG and offering suggestions. Section 2D also references this: 'He later admitted attending an architecture review on day two, suggesting changes, reviewing the code, making 11 commits...'
- **GPT-5.5: Pass.** The memo expressly states that Yoon attended a September 4 MillEdge Pro architecture review at PAG, made suggestions, and later reiterates that he attended an architecture review on day two and suggested changes.

### C-011

ISSUE_004b: Identifies Yoon's admission of reviewing MillEdge Pro codebase ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L99))

- **Sonnet 4.6: Pass.** The memo in Section 2D (PAG duties contradiction) mentions that Yoon 'admitted attending an architecture review on day two, suggesting changes, reviewing the code, making 11 commits, continuing weekly meetings, overseeing MillEdge Pro, and participating in pre-launch review.' It also notes commit messages including 'optimization-engine refactors, engagement-angle parameters, feed-rate logic, convergence criteria, and harmonic-analysis integration.' The memo does reference Yoon reviewing the MillEdge Pro codebase (reviewing the code, making commits). However, the criterion specifically asks whether the memo identifies Yoon's admission of reviewing MillEdge Pro's codebase and/or flagging inefficiencies in it. The memo mentions 'reviewing the code' and making commits with optimization-related changes, which covers the codebase review aspect. The memo does not explicitly mention 'flagging inefficiencies,' but the criterion is satisfied by either the review or the flagging. The memo does identify that Yoon admitted reviewing the MillEdge Pro codebase during September 2024.
- **GPT-5.5: Pass.** The memo expressly states that Yoon admitted reviewing the code, making September commits, attending architecture review, and making suggestions related to MillEdge Pro. This identifies his review of the MillEdge Pro codebase sufficiently under the criterion.

### C-012

ISSUE_004: Flags contradiction with Interrogatory No. 12 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L107))

- **Sonnet 4.6: Pass.** Section 2D of the memo explicitly addresses 'PAG duties --- not involved in development versus technical contributions' and directly references 'Interrogatory Answer No. 12' which states Yoon 'was not involved in development of any CNC optimization product.' The memo then contrasts this with his deposition admissions of attending architecture reviews, making commits, and overseeing MillEdge Pro. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo specifically references Interrogatory No. 12 and flags that Yoon's statement that he was not involved in development of any CNC optimization product conflicts with his deposition admissions about attending architecture reviews, making commits, reviewing code, and overseeing MillEdge Pro.

### C-013

ISSUE_005: Identifies Yoon's misstatement of non-compete radius ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L115))

- **Sonnet 4.6: Pass.** Section 2E of the memo explicitly identifies that 'Yoon testified he believed the restriction was 100 miles and Troy was outside it' while 'The signed Employment Agreement states 150 miles.' This directly flags the discrepancy between Yoon's claimed understanding (100 miles) and the contractual term (150 miles) in Employment Agreement §7(a).
- **GPT-5.5: Pass.** The memo expressly flags the discrepancy in Section 2(E), stating that Yoon testified he believed the non-compete was 100 miles while the signed Employment Agreement states a 150-mile radius.

### C-014

ISSUE_005: Notes strategic significance of radius discrepancy ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L123))

- **Sonnet 4.6: Fail.** The memo in Section 2E mentions that Yoon believed the restriction was 100 miles, that the Employment Agreement states 150 miles, and that the C&D letter identified the 150-mile restriction and Troy's approximate 142-mile distance. However, the memo does not explicitly connect these three data points to show the strategic significance — specifically, that 142 miles falls within the actual 150-mile radius but outside the 100-mile radius Yoon claims he believed applied, making his 'mistake' conveniently self-serving. The memo notes the facts but does not draw the inference that his claimed misunderstanding is strategically convenient because PAG's location at ~142 miles would be prohibited under the real 150-mile radius but permitted under his claimed 100-mile belief. The criterion requires the memo to connect the distance to both radii to show strategic significance, which the memo does not explicitly do.
- **GPT-5.5: Pass.** The memo expressly discusses the discrepancy: Yoon claimed he believed the restriction was 100 miles and that Troy was outside it, while the agreement/C&D/separation documents stated a 150-mile radius and identified Troy as approximately 142 miles away. It also notes this materially tests his claimed understanding and good faith, capturing the strategic significance of the self-serving mistake.

### C-015

ISSUE_006: Identifies suspicious spike in patent file access ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L131))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the suspicious spike in patent file access in Section 1 under 'Patent-file access': 'CMS's DMS log shows 47 AdaptGrip patent-prosecution-file accesses from July 1--August 15, 2024, versus a baseline near 3 per month.' This clearly flags the anomalous increase (roughly 10x or more) as required by the criterion.
- **GPT-5.5: Pass.** The memo expressly flags that CMS's DMS log showed 47 AdaptGrip patent-prosecution-file accesses from July 1 to August 15, 2024, compared to a baseline near 3 per month, and notes the elevated/unexplained activity. Although it does not spell out 'prior 12 months' or calculate '10x,' it identifies the suspicious anomalous spike required by the criterion.

### C-016

ISSUE_006: Notes Yoon's failure to provide business reason for patent access spike ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L139))

- **Sonnet 4.6: Pass.** The memo explicitly addresses this in Section 1 under 'Patent-file access': 'Yoon did not dispute the count, called it CTO oversight, but could not identify a specific project, filing, office action, or deadline explaining the increase.' This directly satisfies the criterion that the memo notes Yoon's inability to provide a specific business reason for the patent access spike despite claiming routine CTO oversight.
- **GPT-5.5: Pass.** The memo expressly notes that Yoon called the increased AdaptGrip patent-file access 'CTO oversight' but could not identify any specific project, filing, office action, or deadline explaining the spike, satisfying the criterion.

### C-017

ISSUE_007: Identifies Yoon told Adwell about non-compete before starting at PAG ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L147))

- **Sonnet 4.6: Pass.** The memo mentions the June 22 dinner and that Yoon 'discussed his non-compete' with Adwell at that time (Section 2C: 'Adwell described a CNC-optimization venture, and they discussed his non-compete'). This indicates the memo does identify that Yoon told Adwell about the non-compete during the June 22 dinner, before starting at PAG. The criterion requires identifying that Yoon admitted telling Adwell about the non-compete during the June 22 dinner, and this is present in the memo.
- **GPT-5.5: Pass.** The memo states that at the June 22 dinner with Adwell, Adwell described a CNC-optimization venture and “they discussed his non-compete,” and places that contact well before Yoon’s September 3 start at PAG. Although not phrased as “Yoon told Adwell,” it identifies that Adwell was informed/discussed the non-compete during the June 22 dinner before PAG employment.

### C-018

ISSUE_007: Connects Adwell's awareness to tortious interference claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L155))

- **Sonnet 4.6: Fail.** The memo discusses Adwell's contact with Yoon and mentions that Yoon testified Adwell told him PAG's counsel had reviewed the situation and thought they were 'fine,' and that the June dinner included discussion of his non-compete. However, the memo does not explicitly connect Adwell's pre-hiring knowledge of the non-compete to a tortious interference claim against PAG, nor does it note that this awareness undermines a PAG defense of ignorance of Yoon's restrictive covenants. The memo treats the non-compete issue primarily as a factual contradiction about Yoon's understanding of the geographic scope (100 vs. 150 miles) and as a contract enforcement matter, without framing Adwell's awareness as significant to a tortious interference theory against PAG.
- **GPT-5.5: Fail.** The memo notes that Adwell discussed or had notice of Yoon's non-compete and recommends deposing him on that issue, but it does not connect Adwell's pre-hiring knowledge to CMS's tortious interference claim against PAG or expressly note that it undermines a PAG defense of lack of awareness of the restrictive covenants.

### C-019

ISSUE_008: Identifies inconsistency re Separation Acknowledgment and USB drive ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L163))

- **Sonnet 4.6: Pass.** The memo clearly identifies this inconsistency in multiple places. In Section 1 under 'Written return/preservation certifications,' it states that Yoon signed a Separation Acknowledgment on August 28 certifying return of all company property and electronic data including USB drives, and specifically certifying he had not copied/transmitted CMS data to a personal account or external medium, yet 'He admitted he did not return the USB and did not disclose the Blue Book email, explaining that he forgot both.' In Section 2A, it further elaborates on this contradiction, noting that Interrogatory 10 says he returned all property, which conflicts with his admission that the drive was at home and had not been returned. The memo explicitly flags the inconsistency between the Separation Acknowledgment certification and Yoon's retention of the USB drive containing the copied files.
- **GPT-5.5: Pass.** The memo expressly states that on August 28 Yoon signed the Separation Acknowledgment certifying return of all company property/electronic data, including USB drives, and that he admitted he did not return the USB. It also links the USB to the 3,847 copied CMS files and flags the conflict with his certifications.

### C-020

ISSUE_008: Notes Yoon's 'forgot about the USB drive' explanation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L171))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 1 under 'Written return/preservation certifications': 'He admitted he did not return the USB and did not disclose the Blue Book email, explaining that he forgot both.' This directly addresses Yoon's 'forgot' explanation for retaining the USB. The memo also notes he signed the Separation Acknowledgment on August 28 certifying return of all company property and that he had not copied/transmitted CMS data, while the USB with 3,847 files remained in his possession at his Troy home. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly states that Yoon signed the August 28 Separation Acknowledgment certifying return of company property/electronic data, admitted he did not return the USB, and explained that he forgot it. It also identifies the USB as containing/copying approximately 3,847 CMS files, satisfying the criterion.

### C-021

ISSUE_009: Identifies Yoon's use of 'harmonic frequency matching' terminology when describing MillEdge Pro ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L179))

- **Sonnet 4.6: Pass.** The memo explicitly identifies that Yoon described MillEdge Pro using 'harmonic frequency matching for tool engagement angles' and notes this wording is also present in CMS's HarmonicPath documentation. This appears in Section 1 under 'Competitive overlap' and is further discussed in Section 3 under 'Technical terminology is a lead, not proof by itself.'
- **GPT-5.5: Pass.** The memo expressly flags that Yoon described MillEdge Pro using the phrase "harmonic frequency matching for tool engagement angles" and notes that the wording also appears in CMS's HarmonicPath documentation.

### C-022

ISSUE_009: Notes Yoon could not cite published source for 'harmonic frequency matching' terminology ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L187))

- **Sonnet 4.6: Pass.** The memo states in Section 3: 'Yoon asserts harmonic analysis and the underlying machining concept are longstanding academic/industry concepts learned before CMS; he could not identify a source for the exact phrase used.' This addresses Yoon's inability to cite a published source for the terminology. However, the criterion specifically requires noting that Yoon claimed it was a 'common industry term' — the memo characterizes his claim as 'longstanding academic/industry concepts' rather than explicitly using 'common industry term.' The substance is captured (he claimed it was a known concept and could not cite a source), and the inability to cite a source is explicitly noted. The criterion says PASS if the memo notes he 'could not cite any published source using that terminology' — this is satisfied. The exact phrasing 'common industry term' vs 'longstanding academic/industry concepts' is a minor difference in wording but the substance matches the criterion's requirements.
- **GPT-5.5: Pass.** The memo expressly addresses the issue in the technical-terminology section, stating that Yoon asserted the concept was longstanding in academic/industry use but “could not identify a source for the exact phrase used.” This captures his inability to cite a published/source reference for the harmonic-frequency-matching terminology.

### C-023

ISSUE_009: Connects terminology to potential trade secret migration ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L195))

- **Sonnet 4.6: Pass.** The memo explicitly flags in Section 1 (Competitive overlap) that Yoon described MillEdge Pro using 'harmonic frequency matching for tool engagement angles,' wording also present in CMS's HarmonicPath documentation. In Section 3 (Evidentiary limits), the memo further notes that 'Technical terminology is a lead, not proof by itself' and instructs counsel to 'Establish whether the specific wording, implementation, parameters, and code are CMS-specific, independently derived, or publicly known.' This directly connects Yoon's use of CMS-proprietary terminology when describing PAG's product to the potential migration of CMS's HarmonicPath algorithm or concepts, which is the core of the trade secret misappropriation claim.
- **GPT-5.5: Pass.** The memo expressly notes that Yoon described PAG's MillEdge Pro using wording also found in CMS's HarmonicPath documentation and treats that terminology overlap as a lead requiring investigation into whether CMS-specific wording, implementation, parameters, or code migrated to PAG. This connects the terminology usage to potential trade secret misappropriation, while appropriately noting it is not proof by itself.

### C-024

ISSUE_010: Identifies factory reset of personal iPhone as spoliation issue ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L203))

- **Sonnet 4.6: Pass.** The memo explicitly identifies that Yoon factory-reset his personal iPhone 15 Pro on September 1, 2024, after receiving CMS's August 22 cease-and-desist/preservation letter (which expressly required preservation of personal-device data). The memo flags this as a potential spoliation concern in Section 1 ('Phone reset after notice') and Section 3 ('Phone reset intent and recoverability are unresolved'), and recommends investigating for a spoliation motion in Section 4. All required elements are present: the device (iPhone 15 Pro), the date (September 1), the prior notice (August 22 C&D letter), and the spoliation flag.
- **GPT-5.5: Pass.** The memo expressly states that Yoon received CMS's August 22 preservation letter, factory-reset his personal iPhone 15 Pro on September 1 deleting potentially relevant data, and later started at PAG on September 3. It also flags the reset as a spoliation issue by discussing intent/recoverability and potential spoliation remedies.

### C-025

ISSUE_010: Notes litigation was reasonably anticipated before reset ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L211))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 1 under 'Phone reset after notice' that Yoon acknowledged receipt of CMS's August 22 cease-and-desist/preservation letter around August 23-24, and that on September 1 he factory-reset his personal iPhone 15 Pro. It further notes that 'The letter expressly required preservation of personal-device data and communications with PAG.' This directly connects the C&D letter date (August 22) to the phone reset date (September 1), establishing that the preservation duty had attached before the phone was wiped. The memo also references this in Section 3 under 'Phone reset intent and recoverability are unresolved,' noting 'The reset followed the preservation notice.' This satisfies the criterion.
- **GPT-5.5: Pass.** The memo connects CMS's August 22 cease-and-desist/preservation letter, Yoon's receipt around August 23–24, and his September 1 phone factory reset. It notes the letter expressly required preservation of personal-device data and that the reset followed the preservation notice, thereby establishing that preservation obligations existed before the wipe.

### C-026

ISSUE_010: Mentions adverse inference or sanctions possibility ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L219))

- **Sonnet 4.6: Pass.** In Section 3 (Evidentiary limits and defenses to anticipate), under the 'Phone reset intent and recoverability are unresolved' bullet, the memo states: 'Determine notice/knowledge, available backups, actual recoverability, and prejudice before seeking a spoliation remedy.' Additionally, in Section 4 (Recommended next steps), item 7 states: 'Evaluate tailored injunctive/preservation relief, damages, and any spoliation motion only after assessing recoverability, intent, prejudice, contract enforceability, and proportionality.' The memo explicitly mentions seeking a 'spoliation remedy' and a 'spoliation motion' in connection with the phone reset, which satisfies the criterion of mentioning the possibility of seeking an adverse inference instruction, sanctions, or other remedies for potential spoliation.
- **GPT-5.5: Pass.** The memo discusses the factory reset as potential spoliation and expressly states that counsel should assess recoverability, intent, prejudice, and proportionality before seeking a spoliation remedy or filing any spoliation motion. This mentions potential judicial remedies for the phone reset-related spoliation issue.

### C-027

ISSUE_011: Notes enforceability question on non-compete scope ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L227))

- **Sonnet 4.6: Pass.** Section 3 of the memo explicitly states: 'Contract remedies require separate legal analysis. The agreement provides an 18-month/150-mile non-compete and 24-month non-solicitation term, but enforceability, scope, reformation, and any current-law issues should be evaluated independently.' This directly identifies that the non-compete's 18-month duration and 150-mile geographic radius may face enforceability challenges, satisfying the criterion.
- **GPT-5.5: Pass.** The memo expressly flags that the 18-month/150-mile non-compete requires separate analysis of enforceability, scope, reformation, and current-law issues, and it discusses the 150-mile radius in connection with Yoon’s understanding. This addresses a potential enforceability issue regarding the non-compete’s scope.

### C-028

ISSUE_011: References Michigan non-compete law or blue-pencil doctrine ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L235))

- **Sonnet 4.6: Fail.** The memo mentions non-compete enforceability and scope in Section 3 ('Contract remedies require separate legal analysis') and notes that 'enforceability, scope, reformation, and any current-law issues should be evaluated independently.' However, it does not reference Michigan's specific non-compete statute (MCL 445.774a), the reasonableness standard under Michigan law, or the blue-pencil/judicial reformation doctrine by name. The reference to 'reformation' is brief and generic, without tying it to Michigan law or the blue-pencil doctrine specifically. The criterion requires reference to Michigan's approach, MCL 445.774a, the reasonableness standard, and/or the blue-pencil doctrine. The memo fails to meet this standard.
- **GPT-5.5: Pass.** The memo does not cite MCL 445.774a or discuss Michigan’s reasonableness standard by name, but it does flag non-compete enforceability and expressly notes that “reformation” of the restrictive covenant requires separate analysis, which satisfies the criterion’s allowance for referencing the possibility of judicial reformation/blue-pencil issues.

### C-029

Assesses significance for trade secret misappropriation claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L243))

- **Sonnet 4.6: Pass.** The memo explicitly connects multiple key admissions to the trade secret misappropriation claim. It discusses the USB transfer of 3,847 files from CMS repositories (OptiMill v3 source, HarmonicPath, AdaptGrip firmware) as evidence of access and transfer of proprietary materials. It addresses the Blue Book email as transfer of a 'restricted customer pricing matrix.' It notes the HarmonicPath terminology overlap with MillEdge Pro as a lead for misappropriation. It discusses the patent file access spike. The Bottom Line section explicitly states what the record does and does not yet establish for the misappropriation claim (e.g., 'The present record does not yet establish that PAG received or used CMS files, that a specific CMS secret was incorporated into MillEdge Pro'). Section 3 addresses evidentiary limits specifically relevant to trade secret claims (no proof of transfer to PAG, independent development defense, terminology not proof by itself). The memo clearly assesses significance of these admissions for the trade secret misappropriation claim throughout.
- **GPT-5.5: Pass.** The memo connects key admissions to the trade secret misappropriation theory by identifying evidence of access and unauthorized transfer of CMS materials, the Blue Book email, HarmonicPath terminology overlap, and patent-file access, while also assessing limits such as lack of present proof of transfer to PAG, actual use, or incorporation of a specific CMS secret into MillEdge Pro. This satisfies the criterion.

### C-030

Assesses significance for breach of non-compete claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L251))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the non-compete claim in Section 2E ('Non-compete understanding — 100 miles claimed versus repeated 150-mile notice'), connecting Yoon's misstatement of the 100-mile radius to the signed Employment Agreement stating 150 miles, the C&D letter identifying Troy's ~142-mile distance, and Yoon's September 3 start at PAG. It also notes in Section 3 that contract remedies require separate legal analysis and that the factual case should not depend solely on the non-compete. Section 2D addresses Yoon's technical involvement in MillEdge Pro despite claiming managerial-only duties. These directly connect admissions to the breach of non-compete claim.
- **GPT-5.5: Pass.** The memo expressly connects admissions to the non-compete claim, including Yoon’s claimed belief that the radius was 100 miles versus the signed 150-mile restriction, PAG’s Troy location at approximately 142 miles, his receipt of notices and separation acknowledgment reciting the 150-mile scope, his start at PAG, and his technical role in MillEdge Pro/competitive overlap. It also flags these facts as material to his understanding and good faith regarding the covenant.

### C-031

Assesses significance for tortious interference claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L259))

- **Sonnet 4.6: Fail.** The memo discusses PAG's hiring of Yoon and Adwell's knowledge of the non-compete (Section 2E notes that 'Adwell told him PAG's counsel had reviewed the situation'), and Section 3 discusses contract remedies. However, the memo never explicitly frames any of these admissions in terms of a tortious interference with business relationships claim against PAG. The memo focuses on trade secret misappropriation, breach of contract, and spoliation issues. While it touches on PAG's knowledge of the non-compete and the hiring timeline, it does not connect these facts to a tortious interference theory or assess their significance for that specific claim. The criterion requires that the memo assess significance of admissions specifically for the tortious interference claim, which it does not do.
- **GPT-5.5: Fail.** The memo discusses recruitment timing, PAG/Yoon communications, and non-compete notice issues, but it does not expressly connect those admissions to CMS’s tortious interference with business relationships claim against PAG or assess their significance for that claim’s elements, such as PAG’s knowledge and intentional interference.

### C-032

Summary table of admissions with cross-references ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L267))

- **Sonnet 4.6: Fail.** The memo contains detailed sections with bullet points and narrative paragraphs listing admissions and contradictions with cross-references to source documents (transcript volumes, interrogatory numbers, forensic report sections, employment agreement sections, etc.). However, the criterion specifically requires a 'summary table (or structured tabular listing)' of admissions/contradictions. The memo does not include any actual table or tabular format — it uses prose paragraphs and bullet lists, but not a table structure. The criterion explicitly states FAIL if no summary table or structured tabular listing is present.
- **GPT-5.5: Pass.** The memo contains structured bullet/lettered listings of material admissions and principal contradictions, and each item includes cross-references to deposition volumes/pages, interrogatory numbers, agreement sections, forensic report sections, and other source documents. Although not a conventional table, it satisfies the criterion's allowance for a structured tabular listing.

### C-033

Recommends motion to compel supplemental interrogatory answers ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L275))

- **Sonnet 4.6: Pass.** Section 4, item 4 explicitly states: 'Serve focused supplemental discovery and consider a continued deposition. Require verified amended answers addressing the USB, file identities/current location, Blue Book email and deletion, all devices/accounts, phone reset/backups, PAG contacts and recruiting dates, actual PAG duties, and the identity/employment-history discrepancies.' This directly recommends seeking supplemental/amended interrogatory answers from Yoon given the contradictions identified throughout the memo.
- **GPT-5.5: Pass.** The memo expressly recommends serving focused supplemental discovery and requiring verified amended answers addressing the USB, Blue Book email, devices/accounts, phone reset, PAG contacts, duties, and identity/employment discrepancies. This directly addresses contradicted interrogatory answers, satisfying the criterion even though it does not specifically say 'motion to compel.'

### C-034

Recommends spoliation sanctions motion or related action ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L283))

- **Sonnet 4.6: Pass.** The memo discusses the phone reset issue in Section 3 (Evidentiary limits) and Section 4 (Recommended next steps). In Section 3, it states: 'Determine notice/knowledge, available backups, actual recoverability, and prejudice before seeking a spoliation remedy.' In Section 4, Step 7, it mentions 'any spoliation motion only after assessing recoverability, intent, prejudice, contract enforceability, and proportionality.' The memo does reference a potential spoliation motion, but frames it as something to consider only after further investigation—it does not affirmatively recommend filing a spoliation sanctions motion or seeking an adverse inference instruction as a concrete next step. The criterion requires that the memo 'recommends (as a next step) filing a motion for spoliation sanctions, seeking an adverse inference instruction, or taking some other specific litigation action related to the factory-reset iPhone.' The memo's treatment is conditional and deferred rather than a recommendation to take action. However, Step 3 of the recommended next steps does recommend investigating the phone reset ('Investigate Gmail and phone recovery'), which is a specific litigation action related to the factory-reset iPhone. The criterion says 'or taking some other specific litigation action related to the factory-reset iPhone.' Step 3 recommends seeking a 'narrow, neutral protocol' for the iPhone/current backups and determining recoverability—this is a specific litigation action related to the factory-reset iPhone. This satisfies the criterion's alternative of 'some other specific litigation action related to the factory-reset iPhone.'
- **GPT-5.5: Pass.** The memo specifically addresses the factory-reset iPhone and recommends related next steps, including investigating phone recovery/backups through a neutral protocol and evaluating a spoliation motion after assessing recoverability, intent, prejudice, and proportionality. This satisfies the requirement for recommending action regarding the spoliation issue.

### C-035

Recommends additional discovery or subpoenas ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L291))

- **Sonnet 4.6: Pass.** The memo's Section 4 (Recommended next steps) contains extensive specific additional discovery recommendations including: obtaining and forensically imaging the USB drive, investigating Gmail and phone recovery through neutral protocols, serving supplemental discovery and considering a continued deposition, deposing Adwell and Quinlan on first contact and hiring timeline, deposing Ravi Chandrasekaran and MillEdge engineers, obtaining complete MillEdge Pro repository history and code diffs, seeking PAG Git repositories and development records, and requesting PAG source code for expert comparison. These clearly satisfy the criterion.
- **GPT-5.5: Pass.** The memo includes a detailed 'Recommended next steps' section with specific additional discovery actions, including preserving and obtaining PAG Git repositories/source-code history, imaging Yoon's USB, seeking Gmail and phone records, serving supplemental discovery, comparing MillEdge Pro source code, and deposing Adwell, Quinlan, Ravi Chandrasekaran, and other PAG personnel.

### C-036

Correct case name ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L299))

- **Sonnet 4.6: Pass.** The memo header clearly identifies the case as 'Corbin Machining Solutions, Inc. v. Derek Yoon and Pinnacle Automation Group, LLC,' which includes Yoon as a defendant. This satisfies the criterion of identifying the case as Corbin Machining Solutions, Inc. v. Yoon (or 'Yoon et al.')
- **GPT-5.5: Pass.** The memo identifies the case as “Corbin Machining Solutions, Inc. v. Derek Yoon and Pinnacle Automation Group, LLC,” which is consistent with Corbin Machining Solutions, Inc. v. Yoon/Yoon et al.

### C-037

Correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L307))

- **Sonnet 4.6: Pass.** The memo header includes 'Kent County Circuit Court No. 24-CV-10583', which correctly identifies the case number as 24-CV-10583.
- **GPT-5.5: Pass.** The memo explicitly identifies the matter as “Kent County Circuit Court No. 24-CV-10583,” which matches the required case number.

### C-038

Correct court ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L315))

- **Sonnet 4.6: Pass.** The memo header identifies the court as 'Kent County Circuit Court No. 24-CV-10583,' which correctly identifies the court as Kent County Circuit Court. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo identifies the case as being in 'Kent County Circuit Court No. 24-CV-10583,' which is an equivalent correct identification of the required court. Although it does not explicitly say Michigan, Kent County Circuit Court is the correct court reference in context.

### C-039

Identifies Interrogatory No. 4 contradiction (first contact with PAG) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L323))

- **Sonnet 4.6: Pass.** Section 2C explicitly addresses the contradiction between Interrogatory No. 4 (which states first contact with Adwell occurred in late August, after resignation) and deposition testimony showing contact as early as June 2024, including a June 22 dinner following a June 8-9 industry event and a July 18 coffee with Quinlan. The memo cites 'Interrogatory Answers Nos. 3--4, 11' and the relevant deposition volumes.
- **GPT-5.5: Pass.** The memo expressly identifies that Interrogatory No. 4 stated Yoon's first contact with Adwell/PAG was in late August after resignation, while deposition testimony and communications showed earlier contact including a June dinner and July/August discussions.

### C-040

Identifies Interrogatory No. 7 contradiction (removal of documents) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L331))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the contradiction between Yoon's Interrogatory No. 7 answer and his deposition testimony in Section 2A, noting that 'Interrogatory 7 says he did not remove or copy any confidential or proprietary documents' while the forensic USB evidence and his own admissions contradict this. It is also referenced in Section 2B regarding the Blue Book. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The memo expressly identifies that Interrogatory No. 7 stated Yoon did not remove or copy confidential/proprietary documents and contrasts that with his deposition admissions and forensic evidence regarding copying files to a USB drive and emailing the Blue Book.

### C-041

Identifies Interrogatory No. 12 contradiction (involvement in CNC products at PAG) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L339))

- **Sonnet 4.6: Pass.** Section 2D of the memo explicitly addresses the Interrogatory No. 12 contradiction, noting that Interrogatory 12 states Yoon 'was not involved in development of any CNC optimization product and his duties were managerial,' while his deposition testimony admitted attending an architecture review, suggesting changes, reviewing code, making 11 commits, continuing weekly meetings, overseeing MillEdge Pro, and participating in pre-launch review. This directly identifies the contradiction between his interrogatory answer and deposition testimony regarding involvement in CNC optimization products at PAG.
- **GPT-5.5: Pass.** The memo explicitly identifies the contradiction: it states that Interrogatory No. 12 said Yoon was not involved in development of any CNC optimization product and had managerial duties, while his deposition admitted architecture-review participation, code review, commits, weekly meetings, oversight, and pre-launch review for MillEdge Pro.

### C-042

References Employment Agreement Section 7(a) for non-compete terms ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L347))

- **Sonnet 4.6: Pass.** The memo explicitly references 'Employment Agreement §7(a)' in Section 2E when discussing the non-compete terms, specifically stating 'The signed Employment Agreement states 150 miles' and citing '(Employment Agreement §7(a); C&D Letter §§I, III--IV; Separation Acknowledgment §3(b), (e); Vol. I at 21--24, 87--89, 176--80; Vol. II at 310--11, 326--30, 340--41.)' It also references Employment Agreement §§7, 10--13 in Section 3 when discussing contract remedies and the 18-month/150-mile non-compete term. The criterion is satisfied.
- **GPT-5.5: Pass.** The memo discusses the non-compete's 150-mile radius and cites the specific provision, "Employment Agreement §7(a)," in the non-compete understanding section. It also references the 18-month/150-mile non-compete elsewhere with Employment Agreement citations.

### C-043

References forensic report for USB and email evidence ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L355))

- **Sonnet 4.6: Pass.** The memo explicitly references the Ridgepoint Digital Forensics Report multiple times when discussing both the USB file transfer and the Blue Book email. For the USB transfer, it cites 'Forensic Report §§5.1, 4.2' and notes the forensic analysis reports 3,847 files / approximately 2.3 GB copied. For the Blue Book email, it cites 'Forensic Report §5.2' and states 'the forensic report says the attachment was an exact, hash-matched copy of CMS's restricted customer pricing matrix.' The report is also listed in the Documents Reviewed section.
- **GPT-5.5: Pass.** The memo explicitly cites the Ridgepoint Digital Forensics Report when discussing the USB transfer (e.g., 3,847 files/2.3 GB and SanDisk drive, Forensic Report §§5.1, 4.2) and the Blue Book email (hash-matched copy sent to Gmail, Forensic Report §5.2).

### C-044

References Separation Acknowledgment document ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L363))

- **Sonnet 4.6: Pass.** The memo explicitly references the Separation Acknowledgment (August 28, 2024) in the context of Yoon's certification of returning all company property and his failure to return the USB drive. In Section 1 under 'Written return/preservation certifications,' the memo states: 'On August 28, Yoon signed a Separation Acknowledgment certifying return of all company property and electronic data, including USB drives, and specifically certifying that he had not copied/transmitted CMS data to a personal account or external medium. He admitted he did not return the USB and did not disclose the Blue Book email, explaining that he forgot both.' The Separation Acknowledgment is also cited multiple times throughout the document with specific section references (§§1--4, §§2, 4, §3(b), (e)) and is listed in the Documents Reviewed section.
- **GPT-5.5: Pass.** The memo expressly references the August 28 Separation Acknowledgment when discussing Yoon’s certification that he returned all company property/electronic data, including USB drives, and his admission that he did not return the USB.

### C-045

References cease-and-desist letter for spoliation timeline ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L371))

- **Sonnet 4.6: Pass.** The memo explicitly references CMS's August 22 cease-and-desist/preservation letter when discussing the phone reset spoliation issue. In Section 1 ('Phone reset after notice'), it states: 'Yoon acknowledged receipt around August 23–24 of CMS's August 22 cease-and-desist/preservation letter. On September 1 he factory-reset his personal iPhone 15 Pro... The letter expressly required preservation of personal-device data and communications with PAG.' This directly establishes the notice timeline connecting the C&D letter (August 22) to the phone reset (September 1). The C&D letter is also cited in the documents reviewed section and referenced multiple times throughout the memo.
- **GPT-5.5: Pass.** The memo expressly states that Yoon received CMS's August 22 cease-and-desist/preservation letter around August 23–24 and then factory-reset his phone on September 1, using the letter to establish notice before the reset.

### C-046

Identifies USB drive details correctly ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L379))

- **Sonnet 4.6: Pass.** The memo correctly identifies all three key details of the USB transfer: 3,847 files, approximately 2.3 GB, and August 10, 2024. These appear in the USB transfer section: 'Forensic analysis reports 3,847 files / approximately 2.3 GB copied from locally synchronized OptiMill v3 source, HarmonicPath, test, and AdaptGrip firmware directories to a SanDisk Ultra 256GB drive on August 10, 2024.' All three specifics are present and correct.
- **GPT-5.5: Pass.** The memo correctly identifies all three required USB transfer details: 3,847 files, approximately 2.3 GB, and the August 10, 2024 date.
