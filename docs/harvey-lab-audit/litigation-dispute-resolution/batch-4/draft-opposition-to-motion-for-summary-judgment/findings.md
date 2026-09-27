# Blind rubric audit

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

```json
{
  "task": "draft-opposition-to-motion-for-summary-judgment",
  "status": "audited",
  "criteria_reviewed": 59,
  "documents_extracted": 15,
  "coverage": "All 59 criteria read and all 15 documents extracted; criterion-bearing passages checked across each document. Legal checks focused on statutory claim validity and burden frameworks. No solver outputs; no exhaustive independent verification of every cited defense case.",
  "confirmed_defects": [
    {
      "criteria": [
        "C-037",
        "C-051"
      ],
      "severity": "high",
      "finding": "Rubric requires constructing and advocating a BSA whistleblower claim under 31 USC \u00a75328 for April\u2013September 2023 events. Section 5328 was repealed January 1, 2021. A legally correct response must identify this defect and assess available claims/amendment rather than silently construct a prima facie case under a repealed statute. Both defense brief and SUMF embed the same false premise.",
      "source": "task.json /criteria/36 and /criteria/50; defendants-msj-brief.docx \u00a7A; defendants-sumf.docx \u00b644",
      "legal_urls": [
        "https://www.fincen.gov/resources/statutes-and-regulations/bank-secrecy-act",
        "https://uscode.house.gov/view.xhtml?edition=2023&num=0&req=granuleid%3AUSC-2023-title31-section5328"
      ],
      "repair": "Revise source case and rubric around applicable current protection. Do not mechanically substitute \u00a75323(g): its (g)(6) bank-employer carveout requires assessment of 12 USC \u00a71831j."
    }
  ],
  "arguable": [
    {
      "criteria": [
        "C-029",
        "C-030",
        "C-039"
      ],
      "finding": "Rebuttal of sweeping federal field preemption is defensible, but lack of express federal preemption does not establish a viable Colorado common-law discharge claim. Colorado law generally precludes duplicative public-policy discharge claims when statutory discharge relief is available. A careful brief may need alternative pleading or distinction; rubric should credit that rather than require unqualified complementary-remedy rhetoric.",
      "legal_url": "https://www.ca10.uscourts.gov/sites/ca10/files/opinions/01019224403.pdf",
      "source": "defendants-msj-brief.docx \u00a7E; C-029\u2013C-030,C-039"
    },
    {
      "criteria": [
        "C-017",
        "C-038",
        "C-046"
      ],
      "finding": "Three-stage prima-facie/legitimate-reason/pretext framework is not the SOX statutory burden. SOX uses contributing-factor causation followed by employer clear-and-convincing same-action defense; Murray rejects a separate retaliatory-intent requirement. These criteria can be satisfied using a framework for another claim, so not categorically defective, but scoring must not force McDonnell Douglas onto SOX.",
      "legal_url": "https://www.supremecourt.gov/opinions/23pdf/22-660_7648.pdf"
    },
    {
      "criteria": [
        "C-027",
        "C-028",
        "C-038",
        "C-049"
      ],
      "finding": "SOX subsidiary status is plausibly satisfied by wholly owned bank and public parent, but statutory text specifies consolidation; BSA/AML concerns are not automatically one of \u00a71514A listed fraud/SEC-law categories. Credit a brief that supplies or investigates the link, rather than assumes every AML complaint is SOX protected."
    }
  ],
  "unverified": [
    {
      "criteria": [
        "C-048"
      ],
      "finding": "Expert report Opinion 1 attributes seven-of-nine TBML red flags to FIN-2023-A001. Primary FinCEN search located FIN-2010-A001 on TBML but not this stated 2023 advisory. Could be a fabricated/miscited authority in the supplied expert report; not confirmed after bounded search. Criterion itself permits citing the expert opinion without adopting advisory identity.",
      "source": "redmond-expert-report.docx Opinion 1 and methods; https://www.fincen.gov/resources/advisories/fincen-advisory-fin-2010-a001"
    }
  ],
  "support_map": {
    "C-001\u2013C-009": "Prompt, motion arguments A\u2013E, standard opposition structure",
    "C-010\u2013C-026": "Hargrove emails, audit, PIP, business plan, Thornburg and Medina declarations, Caldwell deposition, handbook, termination letter",
    "C-027\u2013C-039": "SUMF corporate facts, statutory text and legal sources; Prescott deposition and Redmond report",
    "C-040\u2013C-059": "All source documents collectively; caption; performance review; Hargrove emails; Medina declaration; expert report; handbook; FinCEN/BSA SAR requirements"
  },
  "legal_sources": [
    {
      "url": "https://www.govinfo.gov/content/pkg/USCODE-2020-title31/pdf/USCODE-2020-title31-subtitleIV-chap53-subchapII-sec5323.pdf",
      "point": "\u00a75323(g)(6) excludes employers subject to FDIA \u00a733; source linked by FinCEN includes 2021 amendments."
    },
    {
      "url": "https://www.govinfo.gov/content/pkg/USCODE-2020-title18/pdf/USCODE-2020-title18-partI-chap73-sec1514A.pdf",
      "point": "SOX consolidated subsidiary coverage and enumerated protected subjects."
    }
  ],
  "notes": "Most factual pretext requirements have direct record support. Handbook has documented extraordinary-circumstances exception; deposition record gives basis to argue no approved exception. The public-policy issue is distinguished from proving federal preemption, and no conclusion that all state-law opposition is frivolous is made."
}
```
