Source: https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-2/instruction.md

Source sandbox paths made relative; source email addresses redacted.

# OTB Gang VICAR Trial Jury Instructions — Supplementing brief with new case

Matter: OTB Gang VICAR Trial Jury Instructions

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

- `attachments/Kuhse.pdf`: State v. Kuhse, No. 18-0765, slip op. (Iowa Apr. 8, 2020)
- `attachments/Facts.pdf`: Facts


## Prompt

ASSIGNMENT #2
From: Molly Short ([email redacted])
To: Alexa Pierre ([email redacted])
Re: OTB appeal purpose instruction
Date: July 22, 2026

Hi Alexa,

Thanks for your help on Patton's appeal brief. I found State v. Kuhse, No. 18-0765, slip op. (Iowa Apr. 8, 2020) (Kuhse.pdf), which I didn't see in your initial response. Please supplement your brief with relevant legal analysis of State v. Kuhse. State v. Kuhse, No. 18-0765, slip op. (Iowa Apr. 8, 2020) (Kuhse.pdf) and Facts (Facts.pdf) have been uploaded for your use.

Be sure to limit your review for the Assignment to the attached documents. Do not rely on, reference, or infer any legal authority, factual information, or data beyond what is contained in these uploaded files. If a document is not uploaded, it does not exist for purposes of this analysis. Do not cite external websites, databases, or any source outside the uploaded materials.
