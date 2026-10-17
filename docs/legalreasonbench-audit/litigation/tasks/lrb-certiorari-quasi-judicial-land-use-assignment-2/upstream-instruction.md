Source: https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-2/instruction.md

Source sandbox paths made relative; source email addresses redacted.

# Petition for Writ of Certiorari for Quasi-judicial Proceeding — Brief Requesting Second-Tier Review

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

Write the final complete legal deliverable for this assignment to `response2.md`. The verifier reads only that file.

This is a follow-on assignment. The documents from the previous assignment(s) remain available in `attachments/`, and your prior deliverable `response1.md` is also on disk. Build on that analysis as the prompt directs.

## Attachments

_No new documents for this assignment. The documents from the previous assignment(s) remain available in `attachments/`._

## Prompt

2nd ASSIGNMENT
TO: Denise Swarek, Assistant County Attorney
FROM: Thomas Rowe, County Attorney
RE: PETER SPAHN, ET. AL., V. LEE COUNTY; Case No. 24-CA-1479
DATE: November 10, 2025
________________________________________
The Board has decided to appeal the Order Granting Petition for Certiorari. Draft a ready-to-file brief requesting second-tier review. All legal analysis should be based on the versions of statutes, regulations, and ordinances in effect as of January 1, 2025. Use full Bluebook citation format.
