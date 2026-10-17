Source: https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-3/instruction.md

Source sandbox paths made relative; source email addresses redacted.

# Viability of a DCCA Challenge — Statutory Exceptions

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

Write the final complete legal deliverable for this assignment to `response3.md`. The verifier reads only that file.

This is a follow-on assignment. The documents from the previous assignment(s) remain available in `attachments/`, and your prior deliverable `response2.md` is also on disk. Build on that analysis as the prompt directs.

## Attachments

- `attachments/paperworkers_v_misco.pdf`
- `attachments/wr_grace_v_rubber_workers.pdf`
- `attachments/dc_code_1-605.02.pdf`
- `attachments/fop_doc_labor_comm_v_perb_2009.pdf`
- `attachments/perb_decision_braddock.pdf`


## Prompt

Our firm represents MPD in connection with an arbitration award that reduced Officer Colin Braddock’s termination for excessive force to a 45-day suspension based solely on the arbitrator’s findings regarding Douglas factors six and twelve. PERB affirmed the award in all respects. MPD has been largely unsuccessful in past attempts to persuade the DCCA to set aside PERB decisions affirming arbitration awards, and it is uncertain whether a petition for review is viable here. MPD is extremely dissatisfied with the arbitrator’s handling of Douglas, and it separately believes that being forced to reinstate an officer who shot an unarmed, non-threatening man contravenes a dominant public policy.

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
United Paperworkers Int’l Union v. Misco, Inc., 484 U.S. 29 (1987) (paperworkers_v_misco.pdf)
Fraternal Ord. of Police/Dep’t of Corr. Lab. Comm. v. D.C. Pub. Emp. Rels. Bd., 973 A.2d 174 (D.C. 2009) (fop_doc_labor_comm_v_perb_2009.pdf)

The documents listed above constitute the complete and exclusive universe of materials for this Step. Limit your review to the attached documents. Do not rely on, reference, or infer any legal authority, factual information, or data beyond what is contained in these uploaded files. If a document is not uploaded, it does not exist for purposes of this analysis. All citations must reference the document by its exact name as listed above, followed by the page and paragraph number. Do not cite external websites, databases, or any source outside the uploaded materials.

Complete the following:

1. Set out MPD’s strongest arguments that the Award is contrary to law under D.C. Code § 1-605.02(6) (2016). Anchor each argument in specific findings of the Award and the PERB Decision, with page and paragraph citations, and state the standard the DCCA applies when reviewing a PERB decision affirming an arbitration award as reflected in the uploaded opinions.

2. Set out MPD’s strongest arguments that the Award is on its face contrary to public policy under D.C. Code § 1-605.02(6) (2016). State the test for the public policy exception as articulated in the uploaded opinions, identify the specific documented public policy MPD should invoke and the uploaded source that documents it, and apply the test to the Award. Identify the single weakest point in each of the two arguments and explain why it is the weakest.
