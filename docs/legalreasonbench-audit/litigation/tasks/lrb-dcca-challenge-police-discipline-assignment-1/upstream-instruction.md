Source: https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-1/instruction.md

Source sandbox paths made relative; source email addresses redacted.

# Viability of a DCCA Challenge — Record Mapping: Final Notice Against Award

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

Write the final complete legal deliverable for this assignment to `response1.md`. The verifier reads only that file.

## Attachments

- `attachments/final_notice_adverse_action_braddock.pdf`
- `attachments/comparator_discipline_cases.pdf`
- `attachments/braddock_arbitration_award.pdf`


## Prompt

Our firm represents the District of Columbia Metropolitan Police Department (“MPD”). MPD terminated Officer Colin Braddock after its Internal Affairs Division and Use of Force Review Board found that he used excessive force in an off-duty shooting. On the evening of October 3, 2023, Braddock was at his home in Virginia when his car alarm went off. He saw a man, later identified as Devon Pryor, crouched beside his personal vehicle. Braddock went inside, retrieved his service pistol, and confronted Pryor without calling 911. Pryor, who had dropped his phone under the car while walking home and had hit his head on the frame while reaching for it, stumbled toward Braddock with his hands in his jacket pockets. Braddock fired twice, striking Pryor in the chest and shoulder. Pryor survived after three surgeries and eight months of treatment. MPD issued a Final Notice of Adverse Action on May 22, 2024, finding all twelve Douglas factors aggravating and terminating Braddock. Braddock grieved the termination. On March 14, 2025, an arbitrator reduced the penalty to a 45-day suspension based solely on his findings regarding Douglas factors six and twelve. The D.C. Public Employee Relations Board (“PERB”) affirmed the award in all respects on November 6, 2025. MPD wants to challenge the award at the District of Columbia Court of Appeals (“DCCA”) and has asked us to assess its options. You are the associate assigned to this matter.

The following documents have been uploaded for this Step:
D.C. Metro. Police Dep't, Professional Development Bureau, Final Notice of Adverse Action to Officer Colin R. Braddock, Adverse Action Case No. IS-23-002841, UFRB Case No. 23-UF-0117 (May 22, 2024) (final_notice_adverse_action_braddock.pdf)
In re Arbitration Between Fraternal Ord. of Police/Metro. Police Dep't Lab. Comm. (Braddock Grievance) & D.C. Metro. Police Dep't, FMCS Case No. 24-51267, Grievance No. 24-0392 (Mar. 14, 2025) (Larrabee, Arb.) (braddock_arbitration_award.pdf)
Memorandum from Yolanda Britt, Director, Disciplinary Review Division, Hum. Res. Mgmt. Bureau, D.C. Metro. Police Dep't, to Sandra M. Delgado, Assistant Chief, Professional Development Bureau, re: Comparator Discipline Cases, Adverse Action Case No. IS-23-002841 (Braddock) (Apr. 11, 2024) (comparator_discipline_cases.pdf)

The documents listed above constitute the complete and exclusive universe of materials for this Step. Limit your review to the attached documents. Do not rely on, reference, or infer any legal authority, factual information, or data beyond what is contained in these uploaded files. If a document is not uploaded, it does not exist for purposes of this analysis. All citations must reference the document by its exact name as listed above, followed by the page and paragraph number. Do not cite external websites, databases, or any source outside the uploaded materials.

Complete the following:

1. Reconstruct MPD’s penalty determination as set out in the Final Notice. For each of the twelve Douglas factors, state MPD’s finding and whether MPD treated the factor as aggravating or mitigating, citing the page and paragraph of the Final Notice that supports each answer.

2. Identify every respect in which the Award departs from the Final Notice. For each departure, state the arbitrator’s finding, the standard of review the arbitrator stated he was applying, and the page and paragraph of the Award where each appears. State which Douglas factors the arbitrator left undisturbed.
