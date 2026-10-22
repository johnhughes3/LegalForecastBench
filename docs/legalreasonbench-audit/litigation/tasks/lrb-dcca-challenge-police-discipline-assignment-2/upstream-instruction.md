Source: https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-2/instruction.md

Source sandbox paths made relative; source email addresses redacted.

# Viability of a DCCA Challenge — Scope of Review

Domain: Litigation

Matter: MPD v. PERB

You are a senior legal analyst operating autonomously. You are completing a multi-step legal reasoning task. Follow the role, factual record, instructions, and deliverable requirements provided in the Task and each Assignment.

Each Assignment may require a different legal deliverable. Follow the requirements specific to that Assignment.

## Word limits for court briefs

- A brief in support of or in response to a motion may not exceed **8,750 words**.
- A reply brief may not exceed **3,500 words**.
- For a motion for reconsideration, a brief in support of or in response to the motion may not exceed **3,500 words**, and a reply brief may not exceed **1,750 words**.
- If an Assignment specifies a stricter word limit, follow the stricter limit.

These word limits do not apply to legal memoranda or other non-court-filing deliverables unless the Assignment expressly provides otherwise.

Complete the task end-to-end without asking for confirmation, permission, or clarification.

Use the uploaded matter documents in `attachments/` as your primary case file. You also have internet access via OpenCode's `websearch` tool; use it to research any statutes, regulations, cases, administrative guidance, or secondary authorities that are not supplied as attachments. Cite any authority you rely on in the format requested by the prompt.

For document inspection:
- PDF: `pdftotext attachments/<filename>.pdf -`
- DOCX: `pandoc attachments/<filename>.docx -t markdown`
- XLSX/CSV: use Python with `openpyxl` or `pandas`
- If extraction is unreliable, inspect the raw file with Python libraries or convert/render the relevant pages.

Write the final complete legal deliverable for this assignment to `response2.md`. The verifier reads only that file.

This is a follow-on assignment. The documents from the previous assignment(s) remain available in `attachments/`, and your prior deliverable `response1.md` is also on disk. Build on that analysis as the prompt directs.

## Attachments

- `attachments/douglas_v_veterans_admin.pdf`
- `attachments/dcmr_title6b_1606.pdf`


## Prompt

Our firm represents the District of Columbia Metropolitan Police Department (“MPD”) in connection with an arbitration award that reduced Officer Colin Braddock’s termination for excessive force to a 45-day suspension based solely on the arbitrator’s findings regarding Douglas factors six and twelve. The D.C. Public Employee Relations Board (“PERB”) affirmed the award. MPD is weighing a challenge at the District of Columbia Court of Appeals (“DCCA”). Assume today is March 2, 2026. You are the associate assigned to this matter. The partner has asked you to draft the scope-of-review and preservation analysis for our advice memorandum, based solely on the uploaded materials.

Treat the following as true for all purposes in this matter, whether or not separately memorialized in the record: (a) reasonable minds can disagree as to how comparable the four comparator cases are to Braddock’s case; (b) at no point before the arbitration hearing did Braddock or his union allege that MPD treated similarly situated employees differently; and (c) Braddock knew that MPD intended to rely on the four comparator cases before MPD found him guilty of the excessive force charge.
The following documents have been uploaded for this Step:

D.C. Metro. Police Dep't, Professional Development Bureau, Final Notice of Adverse Action to Officer Colin R. Braddock, Adverse Action Case No. IS-23-002841, UFRB Case No. 23-UF-0117 (May 22, 2024) (final_notice_adverse_action_braddock.pdf)
In re Arbitration Between Fraternal Ord. of Police/Metro. Police Dep't Lab. Comm. (Braddock Grievance) & D.C. Metro. Police Dep't, FMCS Case No. 24-51267, Grievance No. 24-0392 (Mar. 14, 2025) (Larrabee, Arb.) (braddock_arbitration_award.pdf)
Memorandum from Yolanda Britt, Director, Disciplinary Review Division, Hum. Res. Mgmt. Bureau, D.C. Metro. Police Dep't, to Sandra M. Delgado, Assistant Chief, Professional Development Bureau, re: Comparator Discipline Cases, Adverse Action Case No. IS-23-002841 (Braddock) (Apr. 11, 2024) (comparator_discipline_cases.pdf)
Douglas v. Veterans Administration, 5 M.S.P.R. 280 (1981) (douglas_v_veterans_admin.pdf)
D.C. Mun. Regs. tit. 6-B, § 1606 (2017) (dcmr_title6b_1606.pdf)

The documents listed above constitute the complete and exclusive universe of materials for this Step. Limit your review to the attached documents. Do not rely on, reference, or infer any legal authority, factual information, or data beyond what is contained in these uploaded files. If a document is not uploaded, it does not exist for purposes of this analysis. All citations must reference the document by its exact name as listed above, followed by the page and paragraph number. Do not cite external websites, databases, or any source outside the uploaded materials.

Complete the following:

1. State the scope of review the arbitrator was required to apply to MPD’s penalty selection under Douglas and D.C. Mun. Regs. tit. 6-B, § 1606.2 (2017), and assess whether the arbitrator’s treatment of Douglas factors six and twelve stayed within that scope. Address the arbitrator’s requirement that MPD “prove” the comparability of the comparator cases on factor six, and the arbitrator’s finding that a suspension would “likely" have sufficed to deter future misconduct on factor twelve. Support every point with page and paragraph citations to the uploaded materials.

2. State which party bore the burden of production and persuasion on the comparator evidence at each stage of the proceedings, and assess the legal consequence of Braddock’s failure to raise disparate treatment before the arbitration hearing. Identify the strongest position MPD can take on this record and the weakest point in that position, with page and paragraph citations.

Present both analyses as a draft memorandum section that resolves each question with a definite conclusion supported by page and paragraph citations to the uploaded materials.
