# Blind rubric audit

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

```json
{
  "task": "draft-litigation-hold-notice-for-new-product-liability-matter",
  "status": "audited",
  "criteria_reviewed": 61,
  "documents_extracted": 7,
  "coverage": "All 61 criteria read. Seven supplied files extracted (DOCX, EML, all XLSX worksheet cells); inspected criterion-bearing source sections. Not visual review or cell-by-cell validation of unrelated inventory content.",
  "confirmed_defects": [],
  "arguable": [
    {
      "criteria": [
        "C-045"
      ],
      "finding": "Mandatory chronological presentation is an unnecessary format constraint. A memo can correctly prioritize immediate purge suspension or organize actions by responsible team while stating every deadline. Counsel source itself discusses email purge before phone refresh and separately calls Petrosian imaging by June 13 urgent. Failing any later-deadline-first order confuses presentation with operational priority.",
      "source": "task.json /criteria/44; outside-counsel-case-assessment.docx \u00a7\u00a7IV,VI.A\u2013C",
      "repair": "Assess clear urgency and feasible completion deadlines rather than paragraph order."
    },
    {
      "criteria": [
        "C-032"
      ],
      "finding": "Tiering is supported by outside counsel and disproportionate blanket imaging is a fair concern. Still, preserving all 85 devices identically can be reasonable depending on burden; the criterion should allow a justified uniform preservation plan that distinguishes preservation from collection. Do not treat this as proven legal error."
    },
    {
      "criteria": [
        "C-061"
      ],
      "finding": "Narrow June 2 dating is not specified in short prompt; the inventory action deadlines use June 2 as their baseline and supply inferential context. This is therefore a minor inferential formatting restriction rather than a confirmed unsupported date."
    }
  ],
  "unverified": [],
  "support_map": {
    "C-001\u2013C-010": "Prompt; complaint caption; outside counsel memo \u00a7\u00a7I\u2013III; counsel recommended January 1, 2017 ongoing scope",
    "C-011\u2013C-019": "Counsel custodian/data-source sections; inventory custodian/source sheets; IT systems \u00a7\u00a72\u20136",
    "C-020\u2013C-027": "IT migration email and systems summary; Petrosian resignation; counsel \u00a7VI; inventory action sheet",
    "C-028\u2013C-036": "Counsel \u00a7VII and backup discussions; retention policy third-party access rights; complaint \u00b659 personal channels; IT backup section",
    "C-037\u2013C-044": "Counsel compliance/action sections; inventory deadlines; IT migration email",
    "C-046\u2013C-061": "Counsel coordination/compliance sections; inventory action sheet; complaint product allegations; IT and retention policy; served May 28 per counsel memo"
  },
  "legal_sources": [
    {
      "url": "https://www.fjc.gov/content/309290/amendments-federal-rules-practice-and-procedure-civil-rules-2015-failure-preserve",
      "point": "Rule 37(e) supports reasonable preservation and potential consequences, not automatic adverse inference for every loss."
    },
    {
      "url": "https://uscode.house.gov/view.xhtml?edition=2022&req=granuleid%3AUSC-2022-title28a-node88",
      "point": "Rules 26(b)(2)(B) and 34 distinguish inaccessible production sources and possession/custody/control."
    }
  ],
  "notes": "C-029 uses may/contractual control, not a categorical assertion that any supplier data is controlled. Source policy expressly provides rights to request/audit records. C-049 accepts generic consequences; it does not require misstatement of Rule 37 intent threshold. Most apparently over-specific requirements are expressly present in counsel memorandum."
}
```
