Source: https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-5/instruction.md

Source sandbox paths made relative; source email addresses redacted.

# Viability of a DCCA Challenge — Memo to the Client

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

Write the final complete legal deliverable for this assignment to `response5.md`. The verifier reads only that file.

This is a follow-on assignment. The documents from the previous assignment(s) remain available in `attachments/`, and your prior deliverable `response4.md` is also on disk. Build on that analysis as the prompt directs.

## Attachments

_No new documents for this assignment. The documents from the previous assignment(s) remain available in `attachments/`._

## Prompt

Our firm represents the District of Columbia Metropolitan Police Department (“MPD”) in connection with an arbitration award that reduced Officer Colin Braddock’s termination for excessive force to a 45-day suspension based solely on the arbitrator’s findings regarding Douglas factors six and twelve. The D.C. Public Employee Relations Board (“PERB”) affirmed the award. Assume today is March 2, 2026. Prepare the client deliverable based solely on the uploaded materials.
Treat the following as true for all purposes in this matter, whether or not separately memorialized in the record: (a) reasonable minds can disagree as to how comparable the four comparator cases are to Braddock’s case; (b) at no point before the arbitration hearing did Braddock or his union allege that MPD treated similarly situated employees differently; and (c) Braddock knew that MPD intended to rely on the four comparator cases before MPD found him guilty of the excessive force charge.

The following documents have been uploaded for this Step:

D.C. Metro. Police Dep't, Professional Development Bureau, Final Notice of Adverse Action to Officer Colin R. Braddock, Adverse Action Case No. IS-23-002841, UFRB Case No. 23-UF-0117 (May 22, 2024) (final_notice_adverse_action_braddock.pdf)
In re Arbitration Between Fraternal Ord. of Police/Metro. Police Dep't Lab. Comm. (Braddock Grievance) & D.C. Metro. Police Dep't, FMCS Case No. 24-51267, Grievance No. 24-0392 (Mar. 14, 2025) (Larrabee, Arb.) (braddock_arbitration_award.pdf)
Memorandum from Yolanda Britt, Director, Disciplinary Review Division, Hum. Res. Mgmt. Bureau, D.C. Metro. Police Dep't, to Sandra M. Delgado, Assistant Chief, Professional Development Bureau, re: Comparator Discipline Cases, Adverse Action Case No. IS-23-002841 (Braddock) (Apr. 11, 2024) (comparator_discipline_cases.pdf)
Douglas v. Veterans Administration, 5 M.S.P.R. 280 (1981) (douglas_v_veterans_admin.pdf)
D.C. Mun. Regs. tit. 6-B, § 1606 (2017) (dcmr_title6b_1606.pdf)
Opinion No. 1904, PERB Case No. 25-A-09 (D.C. Pub. Emp. Rels. Bd. Nov. 6, 2025) (perb_decision_braddock.pdf)
D.C. Code § 1-605.02 (2016) (dc_code_1-605.02.pdf)
W.R. Grace & Co. v. Local Union 759, 461 U.S. 757 (1983) (wr_grace_v_rubber_workers.pdf)
United Paperworkers Int'l Union v. Misco, Inc., 484 U.S. 29 (1987) (paperworkers_v_misco.pdf)
Memorandum from Marcus T. Bell, Labor Relations Liaison, Hum. Res. Mgmt. Bureau, D.C. Metro. Police Dep't, to Outside Counsel, PERB Case No. 25-A-09 (Braddock), re: Supplemental Comparator Case Identified After Close of Arbitration Record (Feb. 24, 2026) (supplemental_comparator_disclosure.pdf)
Fraternal Ord. of Police/Dep’t of Corr. Lab. Comm. v. D.C. Pub. Emp. Rels. Bd., 973 A.2d 174 (D.C. 2009) (fop_doc_labor_comm_v_perb_2009.pdf)

The documents listed above constitute the complete and exclusive universe of materials for this Step. Limit your review to the attached documents. Do not rely on, reference, or infer any legal authority, factual information, or data beyond what is contained in these uploaded files. If a document is not uploaded, it does not exist for purposes of this analysis. All citations must reference the document by its exact name as listed above, followed by the page and paragraph number. Do not cite external websites, databases, or any source outside the uploaded materials.

Complete the following:

1. Draft the memorandum to MPD addressing (1) the viability of challenging the Award under the public policy exception in D.C. Code sec. 1-605.02(6) and (2) the viability of challenging the Award under the law exception in D.C. Code sec. 1-605.02(6). The memorandum must state the question presented for each exception; state the governing standard for each exception with full Bluebook citations to the uploaded opinions, including pincites; apply each standard to the record, citing the record documents by exact file name with page and paragraph; account for the supplemental comparator; identify the principal weakness of each argument; and close with a recommendation on whether MPD should petition for review, stated as a definite position.
