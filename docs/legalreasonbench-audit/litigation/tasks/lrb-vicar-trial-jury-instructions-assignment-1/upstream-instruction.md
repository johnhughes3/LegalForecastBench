Source: https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-vicar-trial-jury-instructions/steps/assignment-1/instruction.md

Source sandbox paths made relative; source email addresses redacted.

# OTB Gang VICAR Trial Jury Instructions — Appeal brief re: justification instruction

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

Write the final complete legal deliverable for this assignment to `response1.md`. The verifier reads only that file.

## Attachments

- `attachments/Facts.pdf`: Facts
- `attachments/White Horse.pdf`: United States v. White Horse, No. 21-2871, slip op. (8th Cir. June 3, 2022)
- `attachments/702.11.pdf`: Iowa Code § 702.11 (2020)
- `attachments/704.pdf`: Iowa Code ch. 704 (2020)
- `attachments/706.1.pdf`: Iowa Code § 706.1 (2020)
- `attachments/707.11.pdf`: Iowa Code § 707.11 (2020)
- `attachments/708.6.pdf`: Iowa Code § 708.6 (2020)
- `attachments/Ellison.pdf`: State v. Ellison, No. 21-0657, slip op. (Iowa Feb. 3, 2023)
- `attachments/Kehoe.pdf`: United States v. Kehoe, No. 99-2897, slip op. (8th Cir. Nov. 8 2002)
- `attachments/Poe.pdf`: United States v. Poe, No. 05-2914, slip op. (8th Cir. Apr. 6. 2006)
- `attachments/Patton State Plea.pdf`: Patton State Plea


## Prompt

You are an Assistant United States Attorney, practicing law in the Southern District of Iowa. You received the following email from your direct supervisor.

ASSIGNMENT #1
From: Molly Short ([email redacted])
To: Alexa Pierre ([email redacted])
Re: OTB appeal argument section
Date: July 15, 2026

Good morning, Alexa,

Thanks for agreeing to help me draft a section of this appellate brief! You are going to be handling the response to Defendant Raekwon's Patton's argument. Patton was an OTB member, who was involved in a gang-related shooting on May 10, 2020. He was charged with, among other things, attempted murder in aid of racketeering under the VICAR statute (18 U.S.C. § 1959). Although there were a ton of issues at the trial and sentencing, Patton only disputes one major issue on appeal. He contends that the court should have given his requested justification instruction. In short, he argued that the evidence showed that Patton was acting in self-defense when he fired at Raysean Nelson's car. The court declined to give the instruction, and we're taking it up on appeal. 

Please draft the responsive section for this argument, focusing on Patton's claim, the evidence, and the relevant jurisdiction's law. I've already drafted the facts section of this brief, which I've provided below. You can cite to that document, and I will take care of the citations to the trial transcript or rest of the record. That should save you some time. Below is everything you'll need for this project. Our brief is due July 29, 2026.

Facts (Facts.pdf)
Iowa Code § 702.11 (2020) (702.11.pdf)
Iowa Code ch. 704 (2020) (704.pdf)
Iowa Code § 706.1 (2020) (706.1.pdf)
Iowa Code § 707.11 (2020) (707.11.pdf)
Iowa Code § 708.6 (2020) (708.6.pdf)
Patton State Plea (Patton State Plea.pdf)
State v. Ellison, No. 21-0657, slip op. (Iowa Feb. 3, 2023) (Ellison.pdf)
United States v. Kehoe, No. 99-2897, slip op. (8th Cir. Nov. 8 2002) (Kehoe.pdf)
United States v. Poe, No. 05-2914, slip op. (8th Cir. Apr. 6. 2006) (Poe.pdf)
United States v. White Horse, No. 21-2871, slip op. (8th Cir. June 3, 2022) (White Horse.pdf)

Be sure to limit your review for the Assignment to the attached documents. Do not rely on, reference, or infer any legal authority, factual information, or data beyond what is contained in these uploaded files. If a document is not uploaded, it does not exist for purposes of this analysis. All citations must reference the document by its exact name as listed above, followed by the page number, section, or paragraph number if applicable. Do not cite external websites, databases, or any source outside the uploaded materials.
