Source: https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/steps/assignment-1/instruction.md

Source sandbox paths made relative; source email addresses redacted.

# Plaintiff's Response - Forum Non Conveniens — Assignment 1

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

- `attachments/2023 Annual Report Statistical Summary.pdf`: 2023 Annual Report Statistical Summary
- `attachments/Bradbury v. St. Mary's Hospital.pdf`: Bradbury v. St. Mary's Hospital of Kankakee, 273 Ill. App. 3d 555 (Ill. App. 1 Dist. 1995) Case Law
- `attachments/Davis Complaint.docx`: Sara Davis Complaint At Law
- `attachments/Defendants Motion to Transfer.pdf`: Defendants Motion to Transfer
- `attachments/First Am Bank v. Guerine.pdf`: First Nat. Bank v. Guerine, 198 Ill.2d 511 (Ill. 2002) Case Law
- `attachments/Langenhorst v. Norfolk Southern.pdf`: Langenhorst v. Norfolk S. Ry. Co. 219 Ill. 2d 430 (Ill. 2006)


## Prompt

To: Quinn Vivero
From: James Rogers
Re: Davis v. Smith, Forum Non Conveniens
Date: 7/20/2026

Mr. Vivero,

As you are aware, we represent the Davis family for the loss their family suffered when their 23 day old baby passed away last year. We filed our case in June, 2026 in Cook County. On July 14, 2026, the Defendants filed a motion to transfer pursuant to the doctrine of forum non conveniens. 

By way of background, our client, Sara Davis, resides in Kane County, Illinois. She had received her prenatal medical care from Dr. John Smith, who practices in a group called “DuPage Health, S.C.” Both Dr. Smith and DuPage Health, S.C. are DuPage County entities. On August 24, 2024, Sara went into active later and presented to Safe Hospital, located in Naperville, Illinois – which is also DuPage County.
When Sara arrived at the hospital, she was actively bleeding and had stopped feeling movement in her stomach. The doctors and nurses at Safe Hospital hooked her up to a fetal-heart monitor and made the determination that the baby was still doing fine, and would continue to monitor. Over the next two hours as Sara was in active labor, the fetal monitoring records demonstrated decelerations, bradycardia, and tachycardia.

Eventually, when the heart rate had dropped to a dangerously low level, the doctor began attempts to manually deliver through the use of forceps and vacuum. Ultimately he was successful in getting Baby Davis out, however, at birth, Baby Davis demonstrated low APGAR scores, need for resuscitation, and neurological intervention. 

The family was shook by the delivery process and even though Baby Davis was not in good condition, they had him transferred to the Lurie’s Children’s Hospital in Cook County, Illinois. Baby Davis underwent extensive surgical and medical intervention for the next 23 days until he almost passed away on September 16, 2024.

We have retained an expert in this case who believes that Dr. Smith, his group, and the hospital, all deviated from the standard of care in the events leading up to the delayed delivery of Baby Davis. We have filed a wrongful death case for the untimely death and loss of Baby Davis. We have also filed a survival count, which accounts for the damages that Baby Davis sustained during his lifetime. We have spoken with 5 of the Cook County Hospital Doctors who provided care and treatment to Baby Davis. They are all willing to testify that they reviewed the records from Safe Hospital and believe that Dr. Smith deviated from the standard of care in the delivery process, they will also testify to the horrific injuries that Baby Davis sustained throughout his life and discuss how the death was a result initial delay in delivery and further complicated by the various conditions that developed over the next 23 days of his life. They have advised me that they are all Cook County residents and are willing to testify, however, it would be inconvenient for them to take time away from their practice/at the hospital to testify in DuPage rather than Cook County.

We filed the case in Cook County, because venue is appropriate where any part of the action occurred, in a wrongful death case, it also includes the location of death, which in this case is Cook County. DuPage County is not a friendly jurisdiction for a plaintiff against a hospital, both in terms of the overall liability portion but also in the monetary damages portion. Of course, as anticipated, the Defendants are trying to transfer the case to DuPage County.

I have attached the Defendant’s motion for your review. For Assignment #1, review Defendant's motion; for each argument it makes, note what's strong about it, what's weak, and flag any points we should target in our response.

Be sure to limit your review to the attached documents. Do not rely on, reference, or infer any legal authority, factual information, or data beyond what is contained in these uploaded files. If a document is not uploaded, it does not exist for purposes of this analysis. All citations must reference the document by its exact name as listed below, followed by the page and paragraph number. Do not cite to external websites, databases, or any source outside the uploaded materials.

Defendants Motion to Transfer.pdf
Davis Complaint.docx
Bradbury v. St. Mary’s Hospital.pdf
First Am Bank v. Guerine.pdf
Langenhorst v. Norfolk Southern.pdf
2023 Annual Report Statistical Summary.pdf
