# Blind rubric audit

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

```json
{
  "task": "identify-excessive-or-duplicative-research-charges-in-litigation-invoice",
  "status": "audited",
  "criteria_reviewed": 46,
  "documents_extracted": 6,
  "coverage": "All 46 criteria read; all six files extracted and relevant paragraphs inspected. Parsed all 160 July time-entry rows for arithmetic and all 37 RES entries for hours/fees; four worksheet totals checked against detail. No solver outputs.",
  "confirmed_defects": [
    {
      "criteria": [
        "C-025"
      ],
      "severity": "high",
      "finding": "Criterion misstates \u00a76.5. It does not require at least 50% non-research time or reduce an entire entry to a research cap rate. It requires accurate allocation; research over 50% or unclear allocation counts the entire entry toward the cap, while clearly allocated non-research of at least 50% allows only research portion to count. The rubric rewards a false rule that could encourage artificial allocation. Holt June28 email also incorrectly paraphrases the50% rule; packet is internally inconsistent. Detailed \u00a76.5 controls its claimed meaning absent a valid amendment.",
      "source": "terraverde-billing-guidelines.docx \u00a76.5(i)\u2013(iii), extracted lines120\u2013122; task.json /criteria/24",
      "repair": "Require accurate description of classification rule and allocation clarification."
    },
    {
      "criteria": [
        "C-002",
        "C-003",
        "C-006",
        "C-036"
      ],
      "severity": "medium",
      "finding": "Printed fee totals do not reconcile to the complete 160-row time detail: detail sums to $243,080.50 gross, versus cover gross $349,552.50 (difference $106,472). Research detail does sum to $54,104.50. After printed $7,732 discount, detailed net fees are $235,348.50, so research is 19.704% and cap $28,241.82, rather than rubric-required 13.56%/$41,018.46. Quoting cover figures as reported is legitimate; grading should also accept a correctly reconciled alternative and require discrepancy disclosure.",
      "source": "hl-july-2024-invoice.xlsx sheet1 B19\u2013B27 and sheet2 G2:G161; task.json criteria specified",
      "repair": "Reconcile invoice totals or accept cover-vs-detail qualified calculations; do not force false definitive totals."
    },
    {
      "criteria": [
        "C-017"
      ],
      "severity": "medium",
      "finding": "Criterion calls Osei 13 hours essentially one research question. July 8 entry includes drafting a memo and July 10 includes economic-loss-rule analysis. Requiring all 13 hours treated as pure consequential-damages research contradicts the row descriptions and the allocation concern in C-024.",
      "source": "hl-july-2024-invoice.xlsx sheet2 rows21,30; C-017,C-024",
      "repair": "Flag potential excess and seek allocation; permit reasoned assessment rather than mandatory excess conclusion."
    }
  ],
  "arguable": [
    {
      "criteria": [
        "C-022",
        "C-023",
        "C-041"
      ],
      "finding": "\u00a74.3 applies to newly assigned timekeepers. Wendt already billed June MTCA work, so word familiarize alone does not prove new-attorney onboarding. Regulatory-update research can be incremental. A query or conditional hold should pass instead of compulsory full disallowance."
    },
    {
      "criteria": [
        "C-013\u2013C-020",
        "C-028",
        "C-032",
        "C-044",
        "C-045"
      ],
      "finding": "Overlap warrants scrutiny under strict guidelines, but labels alone do not establish identical work. Lost-profit proof versus broader consequential-damage foreseeability, or unjust-enrichment elements versus defenses, may be distinct. Permit a supported conditional adjustment rather than force certainty. \u00a76.4 coordination requirements still provide a valid basis for requesting support."
    },
    {
      "criteria": [
        "C-038"
      ],
      "finding": "Severity rating is not requested in prompt or June 28 email; clear quantified adjustments and priorities can serve the task without Critical/Significant/Minor labels."
    }
  ],
  "unverified": [],
  "support_map": {
    "C-001\u2013C-006": "Guidelines \u00a76.2; Holt email; workbook cover and detail (reconciliation defect noted)",
    "C-007\u2013C-012,C-039": "RES partner entries and rates; \u00a76.3; 5.5*(895-545)=1925 and 7*(725-545)=1260",
    "C-013\u2013C-025": "July RES entry narratives; \u00a7\u00a74.3,6.4\u20136.5",
    "C-026\u2013C-035": "Disbursement sheet D-1/D-10; \u00a79.3; DOE summary 12.5h; June summary14.5h; discount 54104.5*.15=8115.675",
    "C-036\u2013C-046": "Prompt; guidelines; workbook summaries/detail; specific observations above"
  },
  "legal_sources": [],
  "notes": "This is contractual billing-policy review; no substantive legal conclusion depended on external law. Research hours also inconsistent: cover says142.3; detailed timekeeper total137.6. Discount correction $383.675 and individual rate adjustments reconcile independently. Avoid double counting cap, line deletions and discount when combining adjustments."
}
```
