Source: https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/instruction.md

Source sandbox paths made relative; source email addresses redacted.

# Petition for Writ of Certiorari for Quasi-judicial Proceeding — Legal Memorandum to Board of County Commissioners

Domain: Legal

Matter: Petition for Writ of Certiorari for Quasi-judicial Proceeding

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

Write the final complete legal deliverable for this assignment to `response1.md`. The verifier reads only that file.

## Attachments

- `attachments/1774361815-lcu-project.pdf`: LCU Project Detail
- `attachments/1774361815-orderpdf.docx`: Order Granting Petition
- `attachments/1774361815-petition.docx`: Petition for Writ of Certiorari
- `attachments/1774361815-resolution.docx`: Resolution Z-23-035


## Prompt

1st ASSIGNMENT
TO: Denise Swarek, Assistant County Attorney
FROM: Thomas Rowe, County Attorney
RE: PETER SPAHN, ET. AL., V. LEE COUNTY; Case No. 24-CA-1479
DATE: October 27, 2025
________________________________________
We received the attached Order Granting Petition for Writ of Certiorari.  
You are initially provided with the following record as uploaded files. Limit your review to these documents and what legal research is necessary to identify applicable rules and case law relevant to these documents. Do not conduct legal research beyond that. All legal analysis should be based on the versions of statutes, regulations, and ordinances in effect as of January 1, 2025.
•	Resolution Z-23-035 (Resolution.docx)
•	Petition for Writ of Certiorari (Petition.docx)
•	Order Granting Petition (Orderpdf.docx)
•	LCU Project Detail (LCU Project.pdf)
Review only these documents and draft a structured legal memorandum to the Board of County Commissioners that 1) outlines the Order and case history, 2) explains the implications of the Order, 3) identifies options and available actions for Lee County, 4) recommends a legal course of action to the Board. Use full Bluebook citation format.
