# Initial grade-review observations

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-motion-to-dismiss/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-motion-to-dismiss/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

These observations supplement the raw grades. They do not replace or correct any score file. Full-run grading and adjudication remain incomplete.

## Motion to dismiss: Luna xhigh, [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-motion-to-dismiss/task.json#L212)

Run: `repo/results/litigation-dispute-resolution/analyze-counterparty-motion-to-dismiss/gpt6luna-xhigh/20260926-201603/`.

The user-facing task asks for a comprehensive opposition issues memo in DOCX. It does not request severity ratings. [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-motion-to-dismiss/task.json#L212) says PASS for Critical/Significant “or equivalent high-severity language,” and FAIL for Minor or low severity.

The actual memo's executive discussion says that the motion improperly treats remedy limitations as claim-eliminating. Its damages discussion says a cap does not establish that no breach or permissible direct damages exist, and calls the motion's all-or-nothing conclusion too broad. The primary reviewer checked these passages in the original DOCX through a separate Pandoc text extraction (`analysis/luna-motion-output.txt`, lines 31 and 510–512).

Sonnet failed [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-motion-to-dismiss/task.json#L212) while explicitly acknowledging that the memo discusses the point substantively and treats it as important, reasoning that it lacks an explicit severity rating and does not clearly elevate it enough. GPT-5.5 passed the same criterion on the same output.

Classification: documented judge disagreement and a strong disputed false-negative example, compounded by an unrequested severity requirement. The criterion's allowance for equivalent language makes a literal-label demand particularly questionable. Reasonable readers may differ about whether the prose conveys sufficiently high severity; this is not evidence that every disagreement is an error. Preserve both native verdicts and their complete reasoning.

## Motion to dismiss: Luna xhigh, [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-motion-to-dismiss/task.json#L20) and [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-motion-to-dismiss/task.json#L140)

Both judges failed these criteria. Their reasons acknowledge that the memo explains Rule 9(b) particularity and raises Texas CPRC §16.070 against the one-year period, respectively. They fail it for not advancing the rubric's specified inconsistency and unconscionability arguments. The blind legal audit discusses why these requirements are problematic in `batch-1/analyze-counterparty-motion-to-dismiss/audit.md`.

Classification: candidates for faithful application of defective or overly prescriptive rubrics, rather than judges failing to read the output. The underlying legal conclusions should retain the qualifications in the legal audit, especially transaction classification and conflicts rules concerning §16.070. No adjusted score is assigned here.

## Do not limit review to failed grades

The output reviewers also identified a potential substantive model error in both motion memos concerning evidentiary support for counsel's participation. That finding is being checked against the declaration and recorded separately by the motion-review worker. Passing criteria do not establish overall legal accuracy.
