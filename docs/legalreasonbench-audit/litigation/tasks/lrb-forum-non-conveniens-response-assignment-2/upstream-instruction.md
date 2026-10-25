Source: https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-2/instruction.md

Source sandbox paths made relative; source email addresses redacted.

# Plaintiff's Response - Forum Non Conveniens — Assignment 2

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

- `attachments/2023 Annual Report Statistical Summary.pdf`
- `attachments/Bradbury v. St. Mary's Hospital.pdf`
- `attachments/Davis Complaint.docx`
- `attachments/Defendants Motion to Transfer.pdf`
- `attachments/First Am Bank v. Guerine.pdf`
- `attachments/Langenhorst v. Norfolk Southern.pdf`


## Prompt

To: Quinn Vivero
From: James Rogers
Re: Davis v. Smith, Forum Non Conveniens – Response Brief
Date: 7/20/2026

Mr. Vivero,

Thank you for the information you provided to me following your review of the Defendant’s motion to transfer pursuant to forum non conveniens. As I reviewed the information, I think that the best argument that we have is that the burden is on the defendants to show that relevant private and public interest factors “strongly favor” the defendant's choice of forum to warrant disturbing plaintiff’s choice. Given the notes you made, while the Defendants do have some arguments, I do not believe they’ve satisfied their burden. 

For Assignment #2, please draft a response to the Defendants motion to transfer pursuant to the doctrine of forum non conveniens. Please include all affidavits and information you referenced from Assignment #1. 

The names of the physicians from Cook County we have spoken to are: 

•  Liam Vance
•  Savannah Brooks
•  Caleb Montgomery
•  Maya Linwood
•  Garrett Hayes

Be sure to limit your review to the documents provided in Assignment #1. Do not rely on, reference, or infer any legal authority, factual information, or data beyond what is contained in these uploaded files. If a document is not uploaded, it does not exist for purposes of this analysis. All citations must reference the document by its exact name as listed below, followed by the page and paragraph number. Do not cite to external websites, databases, or any source outside the uploaded materials.

Defendants Motion to Transfer.pdf
Davis Complaint.docx
Bradbury v. St. Mary’s Hospital.pdf
First Am Bank v. Guerine.pdf
Langenhorst v. Norfolk Southern.pdf
2023 Annual Report Statistical Summary.pdf
