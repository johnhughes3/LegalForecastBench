# Blind rubric audit

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

```json
{
  "task": "assess-litigation-hold-scope-for-custodian-identification",
  "status": "audited",
  "criteria_reviewed": 50,
  "documents_extracted": 8,
  "coverage": "All 50 criterion texts read. All 8 documents extracted; criterion-bearing portions inspected with targeted searches and section reads. Not a page-by-page visual DOCX review; no solver outputs accessed.",
  "confirmed_defects": [
    {
      "criteria": [
        "C-009"
      ],
      "severity": "low",
      "type": "incomplete pass/fail specification",
      "finding": "PASS requires at least all three named regional managers; FAIL applies only if none is named. Answers naming one or two have no specified outcome.",
      "source": "task.json /criteria/8/match_criteria",
      "repair": "Choose either all-three or at-least-one rule and make PASS and FAIL complements."
    }
  ],
  "arguable": [
    {
      "criteria": [
        "C-034"
      ],
      "finding": "The alternative that SOX creates broader or more protective preservation obligations is imprecise; the sound alternative ties preservation breadth to relevant retaliation communications. Do not call the entire criterion wrong because that valid alternative passes.",
      "source": "task.json /criteria/33/match_criteria; demand-letter-stadler-raines.docx \u00a7\u00a7I,V,VII",
      "repair": "Use relevance to the SOX claim as the stated scope rationale."
    }
  ],
  "unverified": [],
  "support_map": {
    "C-001\u2013C-011": "personnel summary \u00a7\u00a71,4,5; internal investigation \u00a7\u00a7III\u2013IV; email chain Nov 5 and Nov 7",
    "C-012\u2013C-025": "IT memo \u00a7\u00a71\u20136; Nov 6 email; personnel summary \u00a77",
    "C-026\u2013C-028": "SEC letter \u00a7\u00a7I\u2013II; engagement \u00a71; Nov 7 email unified-hold instruction",
    "C-029\u2013C-034": "demand letter \u00a7\u00a7III\u2013V; investigation findings 2; Nov 5\u20137 emails; 18 USC 1514A and Rule 37(e) sources",
    "C-035\u2013C-041": "IT memo \u00a7\u00a71\u20137 and source table; personnel summary \u00a79; GC correspondence",
    "C-042\u2013C-050": "urgent instructions Nov 5\u20137; IT memo retention policies and vendor coordination; investigation recommendation 5; retention policy \u00a7\u00a73,5"
  },
  "legal_sources": [
    {
      "url": "https://www.govinfo.gov/content/pkg/USCODE-2020-title18/pdf/USCODE-2020-title18-partI-chap73-sec1514A.pdf",
      "point": "SOX protection includes qualifying internal reports; supports C-033."
    },
    {
      "url": "https://www.fjc.gov/content/309290/amendments-federal-rules-practice-and-procedure-civil-rules-2015-failure-preserve",
      "point": "ESI sanctions require preservation obligation, unreasonable loss, and inability to restore; no finding that every purge is sanctionable."
    }
  ],
  "notes": "Most apparent specificity is expressly requested in the attached GC email chain. C-031 permits likely/possible early trigger rather than insisting on a categorical date. C-015 asks investigation of recoverability, not a promise that purged chats are recoverable."
}
```
