# Claude Opus 5.5 (low): Extract Key Admissions from Deposition Transcript — Admission Summary Memorandum

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/extract-key-admissions-from-deposition-transcript/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 43 of 46 criteria; GPT-5.5 passed 44 of 46 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [admission-summary-memo.docx](output/admission-summary-memo.docx) ([read as Markdown](output/admission-summary-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | ISSUE_001: Identifies Yoon's first contact with PAG was June 22, 2024 dinner | Pass | Pass |
| [C-002](#c-002) | ISSUE_001: Flags contradiction with Interrogatory No. 4 | Pass | Pass |
| [C-003](#c-003) | ISSUE_001: Notes Yoon was still CTO at time of first PAG contact | Pass | Pass |
| [C-004](#c-004) | ISSUE_002: Identifies Yoon's admission of USB file transfer | Pass | Pass |
| [C-005](#c-005) | ISSUE_002: Flags contradiction with Interrogatory No. 7 | Pass | Pass |
| [C-006](#c-006) | ISSUE_002: Notes Yoon could not identify the 3,847 files | Pass | Pass |
| [C-007](#c-007) | ISSUE_003: Identifies Yoon's admission of emailing Blue Book | Pass | Pass |
| [C-008](#c-008) | ISSUE_003: Flags Yoon's shift from denial to qualified admission on Blue Book email | Pass | Pass |
| [C-009](#c-009) | ISSUE_003: Cross-references forensic report evidence | Pass | Pass |
| [C-010](#c-010) | ISSUE_004a: Identifies Yoon's admission of attending MillEdge Pro technical architecture review | Pass | Pass |
| [C-011](#c-011) | ISSUE_004b: Identifies Yoon's admission of reviewing MillEdge Pro codebase | **Fail** | **Fail** |
| [C-012](#c-012) | ISSUE_004: Flags contradiction with Interrogatory No. 12 | Pass | Pass |
| [C-013](#c-013) | ISSUE_005: Identifies Yoon's misstatement of non-compete radius | Pass | Pass |
| [C-014](#c-014) | ISSUE_005: Notes strategic significance of radius discrepancy | Pass | Pass |
| [C-015](#c-015) | ISSUE_006: Identifies suspicious spike in patent file access | Pass | Pass |
| [C-016](#c-016) | ISSUE_006: Notes Yoon's failure to provide business reason for patent access spike | **Fail** | **Fail** |
| [C-017](#c-017) | ISSUE_007: Identifies Yoon told Adwell about non-compete before starting at PAG | Pass | Pass |
| [C-018](#c-018) | ISSUE_007: Connects Adwell's awareness to tortious interference claim | Pass | Pass |
| [C-019](#c-019) | ISSUE_008: Identifies inconsistency re Separation Acknowledgment and USB drive | Pass | Pass |
| [C-020](#c-020) | ISSUE_008: Notes Yoon's 'forgot about the USB drive' explanation | Pass | Pass |
| [C-021](#c-021) | ISSUE_009: Identifies Yoon's use of 'harmonic frequency matching' terminology when describing MillEdge Pro | Pass | Pass |
| [C-022](#c-022) | ISSUE_009: Notes Yoon could not cite published source for 'harmonic frequency matching' terminology | **Fail** | Pass |
| [C-023](#c-023) | ISSUE_009: Connects terminology to potential trade secret migration | Pass | Pass |
| [C-024](#c-024) | ISSUE_010: Identifies factory reset of personal iPhone as spoliation issue | Pass | Pass |
| [C-025](#c-025) | ISSUE_010: Notes litigation was reasonably anticipated before reset | Pass | Pass |
| [C-026](#c-026) | ISSUE_010: Mentions adverse inference or sanctions possibility | Pass | Pass |
| [C-027](#c-027) | ISSUE_011: Notes enforceability question on non-compete scope | Pass | Pass |
| [C-028](#c-028) | ISSUE_011: References Michigan non-compete law or blue-pencil doctrine | Pass | Pass |
| [C-029](#c-029) | Assesses significance for trade secret misappropriation claim | Pass | Pass |
| [C-030](#c-030) | Assesses significance for breach of non-compete claim | Pass | Pass |
| [C-031](#c-031) | Assesses significance for tortious interference claim | Pass | Pass |
| [C-032](#c-032) | Summary table of admissions with cross-references | Pass | Pass |
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

- **Sonnet 4.6: Pass.** The memo explicitly identifies the June 22, 2024 dinner with Marcus Adwell in multiple places. In Section II.F (Pre-Resignation Contacts with PAG), it states: 'Met Adwell at Michigan Automation Council event (~June 8–9) and dined with him June 22, while CMS CTO; Adwell said he was building something in CNC optimization.' It also notes Yoon 'Told Adwell about his non-compete at the June 22 dinner.' This admission is also referenced in Section III.A and III.B. The memo clearly identifies the June 22 dinner with Adwell and notes they discussed CNC optimization, satisfying the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies Yoon’s admission that he dined with Marcus Adwell on June 22, 2024 while still CMS CTO, and states that Adwell discussed building something in CNC optimization. It also treats this as part of the pre-resignation PAG contacts/admissions.

### C-002

ISSUE_001: Flags contradiction with Interrogatory No. 4 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L27))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Interrogatory No. 4 in Section III.A (Deposition vs. Sworn Interrogatory Answers), stating that Yoon's sworn answer was that he 'First spoke with Adwell "late August 2024 after submitting my resignation," by phone; later phone calls with Adwell and Quinlan in late August.' The memo then flags this as contradicted by the June 8-9 event, June 22 dinner, and other pre-resignation contacts, and notes that Yoon 'conceded answer was inaccurate (Vol. I at 63-64; Vol. II 295:1-12, 308-315, 312:9-19).' This is rated as 'High' impeachment value. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The memo explicitly identifies Interrogatory No. 4, quotes/summarizes Yoon's sworn answer that he first spoke with Adwell in late August after resigning, and flags contrary deposition testimony including the June 22 dinner/contact with Adwell as a high-value contradiction.

### C-003

ISSUE_001: Notes Yoon was still CTO at time of first PAG contact ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L35))

- **Sonnet 4.6: Pass.** The memo notes in Section II.F that Yoon 'Met Adwell at Michigan Automation Council event (~June 8–9) and dined with him June 22, while CMS CTO' (emphasis added). It also states he was 'CMS CTO' at the time of the June 22 dinner, and the timeline shows resignation on August 16. The memo explicitly uses the phrase 'while CMS CTO' to describe his status at the June 22 dinner, directly connecting that he was still employed as CTO during the first PAG contact.
- **GPT-5.5: Pass.** The memo explicitly states that Yoon met Adwell around June 8–9 and dined with him on June 22 “while CMS CTO,” and elsewhere lays out the timeline from June contacts to his August 16 resignation, satisfying the requirement to connect the PAG/Adwell contact with his ongoing CMS employment.

### C-004

ISSUE_002: Identifies Yoon's admission of USB file transfer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L43))

- **Sonnet 4.6: Pass.** The memo clearly identifies Yoon's admission regarding the USB file transfer in Section II.C (USB Transfer, August 10, 2024). It notes that Yoon admitted he 'May have' connected a USB drive and that 'if connected, it was likely mine. No one else used my laptop.' It further documents that he transferred files and copied 'a folder --- or a set of folders' without reviewing them individually. The memo also references the forensic report (Exhibit 14/FR) confrontation and his concession that 'the forensic report traces the files to the OptiMill repository; I recognize it looks bad.' This satisfies the criterion of identifying Yoon's admission that he 'may have' transferred files to a USB drive on August 10, 2024 when confronted with the forensic report.
- **GPT-5.5: Pass.** The memo expressly identifies Yoon’s USB admission, including that he “may have” connected a USB drive, transferred/copied files on August 10, 2024, and that the forensic report traced the files to the OptiMill repository.

### C-005

ISSUE_002: Flags contradiction with Interrogatory No. 7 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L51))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Interrogatory No. 7 in Section III.A (Deposition vs. Sworn Interrogatory Answers). It quotes Rog 7 as stating 'I did not remove or copy any confidential or proprietary documents from CMS.' and then identifies the contrary testimony/evidence as the 3,847 source-code files transferred to USB and the Blue Book sent to Gmail, with citations to Vol. I at 102-108, 132-135 and FR §§5.1-5.2. It rates this as 'High' impeachment value. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly references Interrogatory No. 7, quotes the answer that Yoon did not remove or copy confidential/proprietary documents, and identifies contrary deposition/forensic evidence including the USB transfer of 3,847 source-code files. This directly flags the required contradiction.

### C-006

ISSUE_002: Notes Yoon could not identify the 3,847 files ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L59))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section II.C (USB Transfer) that Yoon 'Transferred files; did not review them individually; copied "a folder --- or a set of folders"; cannot identify or name a single file.' This directly addresses both his failure to review files individually and his inability to identify any specific file transferred. The memo also notes in the Executive Summary that he 'cannot name a single "personal" file.' This satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly states that Yoon “cannot name a single” file and, in the USB Transfer section, that he “did not review them individually” and “cannot identify or name a single file” among the transferred files.

### C-007

ISSUE_003: Identifies Yoon's admission of emailing Blue Book ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L67))

- **Sonnet 4.6: Pass.** Section II.D (Blue Book Email) explicitly identifies Yoon's evolving admission: he went from 'don't recall' to 'may have forwarded it inadvertently,' and the memo notes the sender is his CMS address and recipient is his personal Gmail, with the date August 12, 2024. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly addresses the Blue Book email admission, stating that Yoon admitted the email went from his authenticated CMS account to his personal Gmail and that his account evolved from not recalling to conceding he may have forwarded it inadvertently. It also identifies the Blue Book as the confidential pricing matrix and labels the event as occurring on August 12, 2024.

### C-008

ISSUE_003: Flags Yoon's shift from denial to qualified admission on Blue Book email ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L75))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Yoon's shifting testimony on the Blue Book email in Section II.D, noting his 'Evolving account: "don't recall" → "may have forwarded it inadvertently" while "cleaning out my inbox."' This directly captures both the initial denial/non-recall and the qualified admission with the inadvertent-cleaning explanation. It is also referenced in the contradictions section and the executive summary.
- **GPT-5.5: Pass.** The memo expressly flags Yoon’s evolving Blue Book testimony, stating he moved from “don’t recall” to “may have forwarded it inadvertently,” and also notes the explanation that it occurred while “cleaning out my inbox.”

### C-009

ISSUE_003: Cross-references forensic report evidence ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L83))

- **Sonnet 4.6: Pass.** The memo cross-references Yoon's Blue Book testimony against the Ridgepoint forensic report (FR §5.2) in multiple places. In Section II.D (Blue Book Email), it notes the forensic report shows 'a newly composed, blank-subject, blank-body message — the only such email in August (FR §5.2).' In Section III.C (Testimony vs. Documentary and Forensic Record), it explicitly contrasts Yoon's 'inadvertent forwarding' claim against forensic evidence: 'New standalone message (not a forward), no subject, no body; the only email to any personal account Aug. 1–28; byte-for-byte hash match to \\cms-fs01\Finance\Pricing (FR §5.2).' The memo also references the sender/recipient addresses (CMS address to personal Gmail), the attachment filename ('essentially tells you what the file is'), and the hash match to the file server path. Additionally, Section IV notes a timestamp discrepancy between Vol. I at 133 (11:47 a.m. ET) and the forensic report/Exchange log (14:22:17 EDT, FR §5.2, App. D). This satisfies the criterion of cross-referencing Blue Book testimony against forensic evidence showing email metadata, sender/recipient addresses, and attachment details.
- **GPT-5.5: Pass.** The memo repeatedly cross-references Yoon’s Blue Book testimony with Ridgepoint forensic evidence, including FR §5.2 and App. D. It notes the email was from his CMS account to his personal Gmail, discusses the attachment/filename, cites forensic findings that the message was newly composed with no subject/body, was the only such email in August, and had a byte-for-byte hash match to the Blue Book file. This satisfies the requirement to reference forensic/documentary evidence corroborating the Blue Book email.

### C-010

ISSUE_004a: Identifies Yoon's admission of attending MillEdge Pro technical architecture review ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L91))

- **Sonnet 4.6: Pass.** The memo explicitly identifies in Section II.G (Work on MillEdge Pro) that Yoon 'Attended "MillEdge Pro Technical Architecture Review" on Sept. 4 (day 2); offered suggestions on the optimization engine.' This is cited to Vol. II 298:5--300:3 with a 'Strong' strength rating. The criterion is fully satisfied.
- **GPT-5.5: Pass.** The memo expressly states that Yoon attended the “MillEdge Pro Technical Architecture Review” on Sept. 4, his second day at PAG, and offered suggestions on the optimization engine.

### C-011

ISSUE_004b: Identifies Yoon's admission of reviewing MillEdge Pro codebase ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L99))

- **Sonnet 4.6: Fail.** The criterion requires the memo to identify Yoon's admission of reviewing MillEdge Pro's codebase during September 2024 and/or flagging inefficiencies in it. The memo in Section II.G discusses Yoon's work on MillEdge Pro, including attending the 'MillEdge Pro Technical Architecture Review' on Sept. 4 (day 2), offering suggestions on the optimization engine, making 11 commits, and having commit and admin access. However, the memo does not specifically mention Yoon admitting to reviewing the MillEdge Pro codebase and flagging inefficiencies in it. The memo focuses on his commits and architecture review attendance, but the specific admission about reviewing the codebase and flagging inefficiencies is not explicitly captured. The criterion asks specifically about reviewing the codebase and/or flagging inefficiencies. The memo mentions he 'offered suggestions on the optimization engine' at the architecture review, which could be interpreted as flagging inefficiencies, but this is about the architecture review meeting, not specifically reviewing the codebase. The commits ('optimization engine refactor') suggest he reviewed and modified the codebase, but the memo doesn't explicitly state he admitted to reviewing the MillEdge Pro codebase. Given the close relationship between the described activities (commits, architecture suggestions) and codebase review, and that the memo does describe his involvement with the MillEdge Pro codebase through commits and optimization suggestions, this could be considered sufficient. However, the specific framing of 'reviewing the codebase and flagging inefficiencies' is not explicitly present in the memo.
- **GPT-5.5: Fail.** The memo discusses Yoon's MillEdge Pro involvement, including architecture reviews, suggestions on the optimization engine, commit access, and 11 code commits, but it does not specifically identify an admission that he reviewed the MillEdge Pro codebase in September 2024 or flagged inefficiencies in that codebase.

### C-012

ISSUE_004: Flags contradiction with Interrogatory No. 12 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L107))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Interrogatory No. 12 in multiple places. In Section II.G (Work on MillEdge Pro), it notes that Yoon's Rog 12 answer was 'not as precise as it should have been' and that he conceded involvement 'in my supervisory capacity.' In Section III.A (Deposition vs. Sworn Interrogatory Answers), the table entry for Rog 12 directly quotes his sworn answer as 'General management only; not involved in the development of any CNC optimization products; no hands-on development of features, architectures, or algorithms' and contrasts it with his deposition testimony about attending the architecture review, making 11 commits, attending launch reviews, and weekly standups. This clearly flags the contradiction between his deposition admissions of MillEdge Pro involvement and his Interrogatory No. 12 answer, and rates it as 'High' impeachment value.
- **GPT-5.5: Pass.** The memo explicitly references Interrogatory/Rog 12 several times and identifies that Yoon's deposition testimony about attending architecture reviews, making commits, and otherwise being involved in MillEdge Pro contradicts his interrogatory answer stating he was not involved in development of CNC optimization products.

### C-013

ISSUE_005: Identifies Yoon's misstatement of non-compete radius ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L115))

- **Sonnet 4.6: Pass.** The memo clearly identifies the discrepancy between Yoon's claimed understanding of a 100-mile radius and the actual 150-mile radius in EA §7(a). This appears multiple times: in the Executive Summary ('His "100-mile" belief is refuted by the C&D (Aug. 22) and the Separation Acknowledgment (Aug. 28)'), in Section II.A (the table entry 'Reading §7(a) aloud: "within a 150-mile radius." Concedes he was "mistaken."'), in Section III.B ('Believed the radius was 100 miles until the deposition (Vol. I at 22--24; Vol. II 327:12--19)'), and in Section V.A ('His "100-mile" belief is legally immaterial to breach and factually rebutted by the C&D and SA'). The memo thoroughly flags this discrepancy.
- **GPT-5.5: Pass.** The memo expressly flags Yoon's claimed "100-mile" belief/understanding and contrasts it with Employment Agreement §7(a)'s actual "150-mile radius," including noting that he conceded he was mistaken.

### C-014

ISSUE_005: Notes strategic significance of radius discrepancy ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L123))

- **Sonnet 4.6: Pass.** The memo explicitly notes that Troy is ~142 miles from CMS HQ (Vol. I at 23-24; Vol. II 295:21-296:1), that the actual contractual radius is 150 miles, and that Yoon claimed to believe it was only 100 miles. In Section II.A, it states he 'concedes he was mistaken' about the 100-mile belief. In Section V.A, it notes his '100-mile belief is legally immaterial to breach and factually rebutted by the C&D and SA.' In Section III.C, it highlights that the C&D (Aug. 22) states 150 miles and that Troy (142 mi.) is 'squarely within' it, and that the SA §3(b) recites 150 miles — both signed before his PAG start. The memo clearly connects the ~142-mile distance to both the actual 150-mile radius and the claimed 100-mile belief, showing that 142 miles falls between the two figures, making Yoon's claimed mistake strategically convenient (he would be outside a 100-mile radius but inside the actual 150-mile radius). This satisfies the criterion.
- **GPT-5.5: Pass.** The memo repeatedly notes that Troy/PAG is approximately 142 miles from CMS HQ, that the actual contract radius is 150 miles, and that Yoon claimed he believed the radius was 100 miles. It also flags that the claimed 100-mile belief/PAG counsel’s distance-based conclusion was erroneous and strategically relevant to breach. Although it does not use the exact phrase “outside the 100-mile radius” or “self-serving,” it sufficiently connects the 142-mile distance to both the actual 150-mile term and Yoon’s claimed 100-mile understanding.

### C-015

ISSUE_006: Identifies suspicious spike in patent file access ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L131))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the suspicious spike in patent file access in Section III.C (Testimony vs. Documentary and Forensic Record): 'Patent file access was
- **GPT-5.5: Pass.** The memo expressly flags the patent-file anomaly: it states there were “47 accesses in 46 days vs. 3.0/month baseline (≈10.4x), accelerating toward departure” for patent file access, involving the portfolio matters. Although it does not spell out the July 1–August 15 dates in that row, it identifies the suspicious spike with the required counts, baseline, and approximate 10x increase.

### C-016

ISSUE_006: Notes Yoon's failure to provide business reason for patent access spike ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L139))

- **Sonnet 4.6: Fail.** The memo in Section III.C (Testimony vs. Documentary and Forensic Record) addresses the patent file access spike, noting that Yoon characterized it as 'routine CTO oversight' (Vol. I at 157--159) while the forensic report showed 47 accesses in 46 days vs. a 3.0/month baseline (~10.4x), with no Jira tickets, filings, or deadlines to explain the activity. However, the criterion specifically requires that the memo note Yoon's inability to provide a specific business reason when confronted with the data — e.g., that he said 'I don't recall exactly what I was doing' or similar. The memo notes the absence of supporting documentation (no Jira tickets, filings, or deadlines) but does not record Yoon's own admission that he could not explain or recall the reason for the spike. The memo attributes the characterization to Yoon ('routine CTO oversight') but does not capture that he failed to provide a specific business justification when pressed. The criterion requires the memo to note Yoon's inability to explain, not merely the absence of corroborating records.
- **GPT-5.5: Fail.** The memo mentions Yoon characterized patent file access as “routine CTO oversight” and contrasts that with forensic evidence of a 47-access spike and no Jira tickets, filings, or deadlines. However, it does not note that Yoon himself could not provide a specific business reason or could not recall what he was doing when confronted with the access data. Therefore it does not satisfy the specific criterion.

### C-017

ISSUE_007: Identifies Yoon told Adwell about non-compete before starting at PAG ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L147))

- **Sonnet 4.6: Pass.** The memo explicitly addresses this in Section II.F (Pre-Resignation Contacts with PAG), stating: 'Told Adwell about his non-compete at the June 22 dinner; Adwell: "We should look into that"; considered it "manageable."' (Vol. II 310:8--311:4, rated Strong). It also appears in Section II.A and Section V.C, and in the contradictions table (Section III.B) noting the Vol. I vs. Vol. II discrepancy on when the non-compete disclosure occurred. The memo clearly identifies Yoon's admission that he told Adwell about the non-compete at the June 22, 2024 dinner, before he started at PAG.
- **GPT-5.5: Pass.** The memo explicitly states that Yoon told Marcus Adwell about the non-compete at the June 22 dinner, and elsewhere places that dinner in the pre-resignation/pre-PAG-start timeline before Yoon’s Sept. 3 start date at PAG.

### C-018

ISSUE_007: Connects Adwell's awareness to tortious interference claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L155))

- **Sonnet 4.6: Pass.** In Section V.C ('Claims Against PAG (Tortious Interference / Vicarious or Direct Misappropriation)'), the memo explicitly states: 'PAG had actual knowledge of the non-compete by June 22, 2024, its counsel reviewed it pre-hire, and it put Yoon to work on the competing product immediately with commit and admin access.' This directly connects Adwell's pre-hiring knowledge of the non-compete to the tortious interference claim against PAG, noting that PAG cannot claim ignorance of Yoon's restrictive covenants. The memo also notes the 'fine' conclusion reportedly rested on distance, potentially undermining any good-faith defense. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly notes that Yoon told Adwell about the non-compete before hiring and, in the section on claims against PAG, states that PAG had actual knowledge of the non-compete by June 22 and counsel reviewed it pre-hire. This directly connects Adwell/PAG awareness to the tortious interference claim and undermines any lack-of-knowledge defense.

### C-019

ISSUE_008: Identifies inconsistency re Separation Acknowledgment and USB drive ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L163))

- **Sonnet 4.6: Pass.** The memo explicitly identifies this inconsistency in multiple places. In Section II.E (Separation Acknowledgment), it states: 'Signed SA certifying return of all property including USB drives; did not return the USB drive; did not disclose the Blue Book email; "forgot" both.' In Section III.A (Deposition vs. Sworn Interrogatory Answers), Rog 10 entry states: 'Returned all company property; complied with EA' vs. 'USB drive never returned.' In Section III.C, it notes the SA specifically enumerates USB drives and personal email accounts. The memo clearly flags the inconsistency between the Separation Acknowledgment certification and Yoon's retention of the USB drive containing the 3,847 copied files.
- **GPT-5.5: Pass.** The memo expressly flags the inconsistency: it states that Yoon copied 3,847 source-code files to a USB drive, that the drive remained at his home and was not returned, and that he signed the August 28 Separation Acknowledgment certifying return of all property including USB drives while failing to disclose/return the USB drive. This satisfies the criterion.

### C-020

ISSUE_008: Notes Yoon's 'forgot about the USB drive' explanation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L171))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Yoon's 'forgot' explanation in Section II.E (Separation Acknowledgment), stating: 'Signed SA certifying return of all property including USB drives; did not return the USB drive; did not disclose the Blue Book email; "forgot" both.' It also appears in Section III.C (Testimony vs. Documentary and Forensic Record) where it notes Yoon claimed he 'forgot' the USB drive and email at exit interview, contrasted with the SA specifically enumerating USB drives and the C&D demanding return. The memo also notes the USB drive contained 3,847 source-code files (per the forensic report). All required elements are present: the 'forgot' explanation, the Separation Acknowledgment certification of return of all property, and the fact that he still possessed the drive with approximately 3,847 files.
- **GPT-5.5: Pass.** The memo expressly states that Yoon signed the Separation Acknowledgment certifying return of all property including USB drives, did not return the USB drive, and claimed he “forgot” it. It also repeatedly notes the USB contained 3,847 source-code files and remained at his home/not returned. This satisfies the criterion.

### C-021

ISSUE_009: Identifies Yoon's use of 'harmonic frequency matching' terminology when describing MillEdge Pro ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L179))

- **Sonnet 4.6: Pass.** The memo explicitly identifies in Section II.G (Work on MillEdge Pro) that Yoon 'Described MillEdge Pro as using "harmonic frequency matching for tool engagement angles" --- verbatim HarmonicPath documentation language; cannot identify any outside source for the phrase (before and after redirect).' This is cited at Vol. II 318:20--320:24; 343:1--12 and rated as Strong. The same point is also highlighted in the Executive Summary and in Section V.B on trade secret misappropriation.
- **GPT-5.5: Pass.** The memo explicitly flags that Yoon described MillEdge Pro using the phrase “harmonic frequency matching for tool engagement angles,” characterizing it as verbatim HarmonicPath terminology and noting he could identify no outside source.

### C-022

ISSUE_009: Notes Yoon could not cite published source for 'harmonic frequency matching' terminology ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L187))

- **Sonnet 4.6: Fail.** The memo in Section II.G states: 'Described MillEdge Pro as using "harmonic frequency matching for tool engagement angles" --- verbatim HarmonicPath documentation language; cannot identify any outside source for the phrase (before and after redirect).' This addresses Yoon's inability to cite any published source for the terminology. However, the criterion specifically requires noting that Yoon claimed it was a 'common industry term' before failing to cite a source. The memo does not mention Yoon characterizing it as a 'common industry term' — it only notes he could not identify an outside source. The criterion requires both elements: (1) the claim it was a common industry term, and (2) inability to cite a published source. The memo only captures element (2). That said, re-reading the criterion: 'PASS if the memo notes that Yoon claimed harmonic frequency matching was a common industry term but could not cite any published source.' The memo does not mention the 'common industry term' claim. This is a meaningful omission from the criterion's perspective. However, the memo does note he 'cannot identify any outside source for the phrase (before and after redirect)' which partially satisfies the criterion. The criterion requires noting the 'common industry term' claim specifically. Since the memo omits this specific characterization by Yoon, it does not fully satisfy the criterion as written. But looking more carefully, the criterion says PASS if the memo notes Yoon could not cite a published source — the 'common industry term' part is context. The key element is noting his inability to cite a source, which the memo does address. I'll interpret the criterion as requiring both elements to be present for a PASS. Since the 'common industry term' claim is absent, I'll FAIL this.
- **GPT-5.5: Pass.** The memo expressly states that Yoon used the phrase “harmonic frequency matching for tool engagement angles” and “could identify no outside source” / “cannot identify any outside source for the phrase.” Although it does not use the exact words “common industry term” or “published source,” it addresses the key required point: his inability to cite a source for the terminology.

### C-023

ISSUE_009: Connects terminology to potential trade secret migration ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L195))

- **Sonnet 4.6: Pass.** The memo explicitly flags Yoon's use of the verbatim phrase 'harmonic frequency matching for tool engagement angles' when describing MillEdge Pro, notes this is identical to HarmonicPath documentation language, and directly connects it to the trade secret misappropriation claim. This appears in Section II.G (Work on MillEdge Pro), Section III.C (Testimony vs. Documentary/Forensic Record), Section V.B (Trade Secret Misappropriation analysis), and the recommended next steps regarding a software expert comparison. The memo rates this admission as 'Strong' and explicitly states Yoon 'cannot identify any outside source for the phrase.'
- **GPT-5.5: Pass.** The memo explicitly notes that Yoon described MillEdge Pro using the verbatim HarmonicPath phrase “harmonic frequency matching for tool engagement angles,” could identify no outside source, and treats this as circumstantial support for trade-secret use/disclosure and possible migration of CMS’s HarmonicPath concepts into PAG’s product.

### C-024

ISSUE_010: Identifies factory reset of personal iPhone as spoliation issue ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L203))

- **Sonnet 4.6: Pass.** The memo extensively covers the iPhone factory reset issue. In Section II.H (Phone Reset / Spoliation), it explicitly states that Yoon factory-reset his iPhone 15 Pro on September 1, 2024, with no backup, wiping texts and call logs including communications with Adwell. It notes he received the C&D on August 22-24 and understood it required preservation of communications. The executive summary also flags this as spoliation. Section V.D discusses sanctions and adverse-inference instructions. Section VI recommends a spoliation motion regarding the September 1 factory reset. The memo clearly identifies the phone reset and flags it as a spoliation concern.
- **GPT-5.5: Pass.** The memo expressly identifies that Yoon factory-reset his personal iPhone 15 Pro on September 1, 2024, after receiving the August 22 cease-and-desist/preservation demand, notes that it wiped texts/call logs and lacked a backup, and repeatedly flags it under “Spoliation” with recommendations for sanctions/adverse inference. It also states his PAG start date was September 3, establishing the reset occurred two days before starting.

### C-025

ISSUE_010: Notes litigation was reasonably anticipated before reset ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L211))

- **Sonnet 4.6: Pass.** The memo explicitly connects the August 22 C&D letter to the September 1 phone reset in multiple places. In Section II.H (Phone Reset/Spoliation), it notes Yoon 'Received the C&D Aug. 22--24; understood it required preservation of communications and that litigation was possible' and that he 'Factory-reset his iPhone 15 Pro on Sept. 1, 2024; no backup; texts, call logs, and data wiped.' In Section III.C, it states the C&D 'expressly: You must not perform any factory reset, data wipe, or deletion ... on any device' and that 'He admits receiving and forwarding it to counsel.' The spoliation motion recommendation also references the 'Sept. 1 factory reset' occurring after the hold notice. The memo clearly establishes that the preservation duty attached on August 22 (when the C&D was sent) and that the September 1 reset occurred ten days after that express preservation demand, satisfying the criterion.
- **GPT-5.5: Pass.** The memo expressly connects the August 22 cease-and-desist/preservation demand to the September 1 factory reset, noting Yoon received the C&D before the reset, understood it required preservation and that litigation was possible, and wiped the phone ten days after the preservation demand. This establishes that litigation was reasonably anticipated and the preservation duty had attached before the wipe.

### C-026

ISSUE_010: Mentions adverse inference or sanctions possibility ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L219))

- **Sonnet 4.6: Pass.** The memo explicitly mentions seeking an adverse-inference instruction multiple times. In the Executive Summary, it states the pattern 'supports sanctions under MCR 2.313 and the court's inherent authority, an adverse-inference instruction, and fee-shifting.' In Part VI (Recommended Next Steps), under Motions (15-45 days), it specifically calls for a 'Spoliation motion re: Sept. 1 factory reset (and any post-hold Blue Book deletion) seeking an adverse-inference instruction, fees, and forensic costs.' The memo clearly discusses judicial remedies for the spoliation related to the phone factory reset.
- **GPT-5.5: Pass.** The memo expressly discusses the Sept. 1 factory reset as spoliation and recommends a spoliation/sanctions motion seeking an adverse-inference instruction, fees, and forensic costs.

### C-027

ISSUE_011: Notes enforceability question on non-compete scope ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L227))

- **Sonnet 4.6: Pass.** Section V.A explicitly addresses the enforceability question under MCL 445.774a, noting the contest will be on reasonableness, and references the 150-mile radius, the senior executive role, access to trade secrets, direct product overlap, and the reformation clause (EA §7(c)). It also notes the defense argument on the 150-mile radius and absence of separate consideration. This satisfies the criterion of identifying potential enforceability/reasonableness challenges regarding the non-compete's scope.
- **GPT-5.5: Pass.** The memo expressly flags that enforceability will turn on reasonableness under MCL 445.774a and anticipates defense arguments regarding the 150-mile radius, while discussing the non-compete’s 18-month/150-mile terms and competitive scope. This satisfies the requirement to note a potential reasonableness challenge to the non-compete’s scope.

### C-028

ISSUE_011: References Michigan non-compete law or blue-pencil doctrine ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L235))

- **Sonnet 4.6: Pass.** In Section V.A (Breach of Non-Compete), the memo explicitly references 'MCL 445.774a' as the governing Michigan statute and the 'reasonableness' standard under that statute. It also references the 'reformation clause (EA §7(c))' which relates to the blue-pencil/reformation doctrine. These references satisfy the criterion requiring mention of Michigan non-compete law, the reasonableness standard, and judicial reformation authority.
- **GPT-5.5: Pass.** The memo expressly references Michigan non-compete law in Part V.A, including reasonableness under MCL 445.774a and the relevance of a reformation clause, satisfying the criterion.

### C-029

Assesses significance for trade secret misappropriation claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L243))

- **Sonnet 4.6: Pass.** The memo extensively connects key admissions to the trade secret misappropriation claim. Section V.B is explicitly titled 'Trade Secret Misappropriation (MUTSA / DTSA) and Breach of Confidentiality (EA §8)' and directly addresses the USB transfer (unauthorized copying, premeditation evidence), the Blue Book email, the verbatim HarmonicPath phrasing used by Yoon to describe MillEdge Pro, the commit 'harmonic analysis integration,' and the patent file access patterns. The memo also discusses acquisition by improper means, use/disclosure gaps, and circumstantial evidence. Throughout Parts II and III, these admissions are catalogued with their evidentiary strength and relevance. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The memo expressly includes a section on “Trade Secret Misappropriation (MUTSA / DTSA)” and connects key admissions/evidence to that claim, including unauthorized USB copying, Blue Book transfer, HarmonicPath terminology, related commits, and circumstantial evidence of use. It also discusses patent file access as contrary forensic evidence. This satisfies the criterion.

### C-030

Assesses significance for breach of non-compete claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L251))

- **Sonnet 4.6: Pass.** The memo extensively addresses the breach of non-compete claim. Section II.A is entirely dedicated to non-compete admissions, covering Yoon's acknowledgment of the 150-mile radius, the ~142-mile distance to Troy, his understanding of the agreement, and PAG's competitive overlap. Section V.A explicitly analyzes the significance of these admissions for the breach of non-compete claim under MCL 445.774a, noting that 'formation, knowledge, and competing employment within the territory are effectively conceded.' The memo also connects the 100-mile vs. 150-mile discrepancy to the C&D and Separation Acknowledgment, and discusses PAG's knowledge of the non-compete. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly connects admissions to CMS's breach of non-compete claim, including the signed agreement, 150-mile radius versus Yoon's claimed 100-mile belief, PAG/Troy being approximately 142 miles away, direct competition through MillEdge Pro, and Yoon's competing work. Section V.A specifically assesses their significance for breach of EA §7(a).

### C-031

Assesses significance for tortious interference claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L259))

- **Sonnet 4.6: Pass.** Section V.C explicitly addresses 'Claims Against PAG (Tortious Interference / Vicarious or Direct Misappropriation)' and connects specific admissions to the tortious interference claim: PAG had actual knowledge of the non-compete by June 22, 2024 (from Yoon's admission that he told Adwell about it at the June 22 dinner), PAG's counsel reviewed it pre-hire, and PAG put Yoon to work on the competing product immediately. The memo also notes the potential advice-of-counsel issue with Mr. Kellner. These directly connect admissions to the tortious interference claim against PAG.
- **GPT-5.5: Pass.** The memo expressly includes a section titled “Claims Against PAG (Tortious Interference / Vicarious or Direct Misappropriation)” and connects admissions such as Adwell’s knowledge of the non-compete, PAG counsel’s review, and PAG putting Yoon to work on a competing product to the significance of a tortious interference claim against PAG.

### C-032

Summary table of admissions with cross-references ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L267))

- **Sonnet 4.6: Pass.** The memo contains multiple structured summary tables throughout Part II (Sections A through H) and Part III (Sections A through D). Each table lists admissions or contradictions with explicit cross-references to deposition transcript volumes and page/line numbers, interrogatory numbers (Rog 3, 4, 6, 7, etc.), Employment Agreement sections (EA §7, §8, §9, etc.), and forensic report sections (FR §5.1, §5.2, etc.). The tables include columns for the admission/contradiction, citation, and strength/value ratings. This clearly satisfies the criterion of a summary table of admissions with cross-references to source documents.
- **GPT-5.5: Pass.** The memo includes multiple structured tables listing key admissions by topic, with columns for Admission, Cite, and Strength, and extensive cross-references to deposition pages/lines, interrogatory numbers, Employment Agreement sections, forensic report sections, and other source documents. It also includes contradiction tables with source references.

### C-033

Recommends motion to compel supplemental interrogatory answers ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L275))

- **Sonnet 4.6: Pass.** The memo explicitly recommends serving a formal deficiency letter demanding supplementation/correction of Rogs 3, 4, 6, 7, 11, 12, 14, and 15 under MCR 2.302(E) in the 'Immediate (0--14 days)' section of Part VI. This directly satisfies the criterion of recommending action to seek supplemental or amended interrogatory answers given the contradictions between Yoon's interrogatory responses and deposition testimony.
- **GPT-5.5: Pass.** The memo expressly recommends demanding corrected/supplemented interrogatory answers, including in the Executive Summary and Immediate Next Steps, where it calls for a deficiency letter demanding supplementation/correction of contradicted interrogatory responses under MCR 2.302(E). This satisfies the criterion.

### C-034

Recommends spoliation sanctions motion or related action ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L283))

- **Sonnet 4.6: Pass.** The memo explicitly recommends filing a spoliation/sanctions motion in multiple places. In the Executive Summary it states '(2) file a spoliation/sanctions motion seeking an adverse-inference instruction.' In Part VI under 'Motions (15-45 days)' it details: 'Spoliation motion re: Sept. 1 factory reset (and any post-hold Blue Book deletion) seeking an adverse-inference instruction, fees, and forensic costs.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly recommends spoliation-related action: in the Executive Summary it recommends filing a spoliation/sanctions motion seeking an adverse-inference instruction, and in the Motions section it specifically calls for a spoliation motion regarding the Sept. 1 factory reset seeking adverse inference, fees, and forensic costs.

### C-035

Recommends additional discovery or subpoenas ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L291))

- **Sonnet 4.6: Pass.** The memo extensively recommends additional discovery actions throughout Part VI, including: subpoenas to Sycamore Ventures, Google (Gmail), Apple, and Yoon's wireless carrier; depositions of Marcus Adwell, Teresa Quinlan, Ravi Chandrasekaran, Lisa Marchetti, James Parekh, Kevin Matsuda, and Karen Villalobos; document requests to PAG for the full MillEdge Pro repository with git history, architecture documents, benchmarking data, recruiting files, and communications; motions to compel turnover of the USB drive and forensic imaging of personal devices and Gmail; and retention of a software expert to compare MillEdge Pro against OptiMill/HarmonicPath. These are all specific additional discovery recommendations well beyond what has already occurred.
- **GPT-5.5: Pass.** The memo recommends numerous specific additional discovery actions, including compelling turnover/imaging of Yoon’s USB drive, Gmail, and personal devices; subpoenaing Google, Apple, Yoon’s carrier, and Sycamore; requesting PAG’s MillEdge Pro repository/source code and related records; and deposing Marcus Adwell, Teresa Quinlan, Ravi Chandrasekaran, and others.

### C-036

Correct case name ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L299))

- **Sonnet 4.6: Pass.** The memo's RE line states: 'Corbin Machining Solutions, Inc. v. Derek Yoon and Pinnacle Automation Group, LLC, Kent County Circuit Court Case No. 24-CV-10583.' This correctly identifies the case as Corbin Machining Solutions, Inc. v. Yoon (et al.), satisfying the criterion.
- **GPT-5.5: Pass.** The memo identifies the matter as “Corbin Machining Solutions, Inc. v. Derek Yoon and Pinnacle Automation Group, LLC,” which is consistent with Corbin Machining Solutions, Inc. v. Yoon / Yoon et al.

### C-037

Correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L307))

- **Sonnet 4.6: Pass.** The memo clearly identifies the case number as 24-CV-10583 in the RE line of the memorandum header: 'Corbin Machining Solutions, Inc. v. Derek Yoon and Pinnacle Automation Group, LLC, Kent County Circuit Court Case No. 24-CV-10583'
- **GPT-5.5: Pass.** The memo's RE line identifies the case as Kent County Circuit Court Case No. 24-CV-10583, which matches the required case number.

### C-038

Correct court ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L315))

- **Sonnet 4.6: Pass.** The memo's header clearly identifies the court as 'Kent County Circuit Court Case No. 24-CV-10583,' which correctly identifies the court as Kent County Circuit Court in Michigan (the case caption references Michigan law throughout). This satisfies the criterion.
- **GPT-5.5: Pass.** The memo identifies the matter as pending in 'Kent County Circuit Court Case No. 24-CV-10583,' which is the correct court identification for Kent County Circuit Court, Michigan or an equivalent correct identification.

### C-039

Identifies Interrogatory No. 4 contradiction (first contact with PAG) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L323))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the Interrogatory No. 4 contradiction in Section III.A (Deposition vs. Sworn Interrogatory Answers). It notes that Rog 4 stated Yoon first spoke with Adwell 'late August 2024 after submitting my resignation,' while deposition testimony revealed contact as early as June 8-9 at the Michigan Automation Council event, the June 22 dinner, emails in June/July/August, and a mid-July in-person coffee with Quinlan. The memo rates this as 'High' impeachment value and cites Vol. I at 63-64 and Vol. II 295:1-12, 308-315, 312:9-19 as contrary testimony. It is also referenced in the Executive Summary and in Section II.F on pre-resignation contacts.
- **GPT-5.5: Pass.** The memo explicitly identifies the Interrogatory No. 4 contradiction, stating that Yoon’s sworn answer claimed first contact with Adwell/PAG was in late August after resignation, while deposition testimony and evidence showed contacts beginning at the June 8–9 event, June 22 dinner, mid-July coffee, and other pre-resignation communications.

### C-040

Identifies Interrogatory No. 7 contradiction (removal of documents) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L331))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Interrogatory No. 7 in Section III.A (Deposition vs. Sworn Interrogatory Answers). It states that Yoon's sworn answer to Rog 7 was 'I did not remove or copy any confidential or proprietary documents from CMS,' and contrasts this with his deposition testimony admitting to transferring 3,847 source-code files to a USB drive and the Blue Book to Gmail, and conceding the Blue Book is Proprietary Information. This is rated 'High' impeachment value.
- **GPT-5.5: Pass.** The memo expressly identifies Interrogatory No. 7, quotes Yoon’s sworn answer that he did not remove or copy confidential/proprietary documents, and contrasts it with deposition/forensic evidence of source-code copying to USB and the Blue Book email to Gmail.

### C-041

Identifies Interrogatory No. 12 contradiction (involvement in CNC products at PAG) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L339))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Interrogatory No. 12 in multiple places. In Section II.G (Work on MillEdge Pro), it notes that Yoon's Rog 12 answer was 'not as precise as it should have been' and that he conceded involvement 'in my supervisory capacity.' In Section III.A (Deposition vs. Sworn Interrogatory Answers), the table entry for Rog 12 states the sworn answer was 'General management only; not involved in the development of any CNC optimization products; no hands-on development of features, architectures, or algorithms,' and contrasts this with contrary testimony about attending the architecture review on day 2, making 11 commits, participating in launch reviews, and attending weekly MillEdge standups. This is rated 'High' impeachment value. The contradiction is clearly and thoroughly identified.
- **GPT-5.5: Pass.** The memo explicitly identifies that Yoon’s sworn Interrogatory No. 12 answer denied involvement in CNC optimization product development at PAG, while his deposition testimony admitted architecture review attendance, commits, launch reviews, standups, and supervisory involvement with MillEdge Pro. It also notes he conceded the answer was imprecise/inaccurate.

### C-042

References Employment Agreement Section 7(a) for non-compete terms ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L347))

- **Sonnet 4.6: Pass.** The memo explicitly references 'EA §7(a)' multiple times when discussing the non-compete terms, including in the section header 'A. Employment Agreement / Non-Compete (EA §7(a))' and in Part V.A 'Breach of Non-Compete (EA §7(a))'. The 150-mile radius and 18-month duration are discussed in direct connection with this specific section of the Employment Agreement.
- **GPT-5.5: Pass.** The memo expressly identifies the non-compete as Employment Agreement §7(a), including in the section heading and discussion of the 150-mile radius and competing employment, and later references breach of non-compete under EA §7(a).

### C-043

References forensic report for USB and email evidence ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L355))

- **Sonnet 4.6: Pass.** The memo extensively references the Ridgepoint Forensic Report (cited as 'FR §§...' throughout) when discussing both the USB file transfer and the Blue Book email. For the USB transfer, it cites FR §§5.1, 5.4.1 noting all 3,847 files were source code copied from a full repository clone. For the Blue Book email, it cites FR §5.2 noting it was a newly composed message with a byte-for-byte hash match to the CMS finance server. These references appear in the executive summary, the admission tables, and the contradictions section.
- **GPT-5.5: Pass.** The memo explicitly lists the Ridgepoint Forensic Report as a source and repeatedly cites forensic report sections when discussing both the USB transfer (e.g., FR §§5.1, 5.4.1) and the Blue Book email (e.g., FR §5.2), including specific forensic findings about file types, source repository, email composition, hashes, and logs.

### C-044

References Separation Acknowledgment document ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L363))

- **Sonnet 4.6: Pass.** The memo extensively references the Separation Acknowledgment (dated August 28, 2024) in multiple sections. In Section II.E, it has an entire subsection dedicated to the Separation Acknowledgment, noting that Yoon 'signed SA certifying return of all property including USB drives; did not return the USB drive; did not disclose the Blue Book email; "forgot" both.' It also references the SA in the contradictions section (III.A, Rog 10) and in the documentary evidence section (III.C), specifically citing SA §§1(d), 2(a)-(b), 4(c) which enumerate USB drives and personal email accounts. The SA is listed as a source document in the header and is cited throughout in connection with Yoon's false certification of returning all company property including the USB drive.
- **GPT-5.5: Pass.** The memo explicitly lists the Separation Acknowledgment dated August 28, 2024 as a source and repeatedly references it when discussing Yoon’s certification that he returned all company property, including USB drives, while admitting he did not return the USB drive.

### C-045

References cease-and-desist letter for spoliation timeline ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L371))

- **Sonnet 4.6: Pass.** The memo explicitly references the cease-and-desist letter dated August 22, 2024 in the context of the spoliation issue. In Section II.H (Phone Reset / Spoliation), it states Yoon 'Received the C&D Aug. 22--24; understood it required preservation of communications and that litigation was possible' and that he 'Factory-reset his iPhone 15 Pro on Sept. 1, 2024.' In Section III.C, it notes 'C&D §VI expressly: "You must not perform any factory reset, data wipe, or deletion ... on any device." He admits receiving and forwarding it to counsel.' The memo clearly connects the August 22 C&D letter to the September 1 phone reset to establish Yoon was on notice before the spoliation occurred.
- **GPT-5.5: Pass.** The memo expressly ties the September 1, 2024 iPhone factory reset to CMS's cease-and-desist letter, including the August 22, 2024 date and preservation language. It states Yoon received the C&D on Aug. 22–24, understood preservation obligations, and reset the phone afterward, establishing notice before the reset.

### C-046

Identifies USB drive details correctly ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L379))

- **Sonnet 4.6: Pass.** The memo correctly identifies the file count (3,847 files) and the date (August 10, 2024) of the USB transfer in multiple places. However, it does not mention the data size of approximately 2.3 GB anywhere in the document. The criterion requires at least two of the three specifics (file count, data size, date) to be correct. Since two of the three are correctly stated (file count and date), the criterion is satisfied.
- **GPT-5.5: Pass.** The memo correctly identifies the USB transfer as occurring on August 10, 2024 and states that 3,847 files were copied/transferred. Although it does not mention the approximately 2.3 GB data size, it provides at least two of the three required specifics.
