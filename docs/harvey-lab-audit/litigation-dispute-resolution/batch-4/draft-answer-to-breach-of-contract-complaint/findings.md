# Blind rubric audit

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-answer-to-breach-of-contract-complaint/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-answer-to-breach-of-contract-complaint/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

```json
{
  "task": "draft-answer-to-breach-of-contract-complaint",
  "status": "audited",
  "criteria_reviewed": 40,
  "documents_extracted": 12,
  "coverage": "All 40 criterion texts read; all 12 source files extracted and criterion-bearing passages inspected. Text/structural review, not visual rendering. No solver output.",
  "confirmed_defects": [
    {
      "criteria": [
        "C-005"
      ],
      "severity": "medium",
      "finding": "Title requires every complaint paragraph, but PASS accepts only 50 of the actual 91 numbered allegations; FAIL threshold is fewer than 40, leaving 40\u201349 undefined. A materially incomplete answer can pass.",
      "source": "task.json /criteria/4; complaint-meridian-v-caldwell.docx numbered paragraphs 1\u201391",
      "repair": "Require responsive treatment of all 91 allegations, including Rule 8(b)(5) lack-of-knowledge responses where appropriate."
    },
    {
      "criteria": [
        "C-014"
      ],
      "severity": "medium",
      "finding": "Mandatory liability limit omits a second express Section 13.2 obligation: reasonable documented non-cancellable raw-material costs, subject to mitigation and PO cap. Saying liability is limited to manufactured/in-process goods misstates the attached contract.",
      "source": "master-supply-agreement.docx \u00a713.2 (extracted line 93); task.json /criteria/13",
      "repair": "Include both manufactured/in-process conforming goods and qualifying raw-material costs."
    },
    {
      "criteria": [
        "C-017"
      ],
      "severity": "medium",
      "finding": "The explanatory correct-interest calculation assumes November 1, 2024 as due date without source support. MSA \u00a77.1 makes payment due 45 days after acceptance/deemed acceptance, not a fixed November 1 date, and \u00a77.4 suspends interest on qualifying disputed amounts. Challenging the claimed interest is sound; the rubric should not label $78,720 the correct figure.",
      "source": "master-supply-agreement.docx \u00a7\u00a76.1\u20136.2,7.1,7.3\u20137.4; task.json /criteria/16",
      "repair": "Require challenge tied to acceptance, due-date and dispute assumptions, not this supposedly correct amount."
    }
  ],
  "arguable": [
    {
      "criteria": [
        "C-008",
        "C-009"
      ],
      "finding": "Compelled force-majeure defense is weak on these facts but not demonstrated frivolous: MSA \u00a712.1 is nonexclusive and the rubric allows alternatives. Do not classify disputed advocacy as definitively unlawful."
    },
    {
      "criteria": [
        "C-011"
      ],
      "finding": "Blanket duty to resell overstates the UCC remedies framework; \u00a72-706 describes an available resale remedy, while inability reasonably to resell matters to a price action under \u00a72-709. General mitigation challenge is supported. Georgia primary-source verification of the precise resale proposition remains incomplete."
    },
    {
      "criteria": [
        "C-025"
      ],
      "finding": "Separate reservations section is unrequested boilerplate; amendment is controlled by Rule 15, not preserved by a unilateral reservation. Courts vary on striking these clauses, so including one is not categorically wrong.",
      "legal_url": "https://ecf.ksd.uscourts.gov/cgi-bin/show_public_doc?2024cv2230-39="
    },
    {
      "criteria": [
        "C-026"
      ],
      "severity": "medium",
      "finding": "Mandatory with-prejudice dismissal conflicts with the substantial jurisdictional problem apparent on the supplied allegations: plaintiff has its principal place of business in Georgia and all defendant LLC members are alleged Georgia citizens. A jurisdictional dismissal is not a merits dismissal with prejudice. A merits-based alternative prayer can be proper; classify as arguable, not a confirmed defect.",
      "source": "complaint-meridian-v-caldwell.docx \u00b6\u00b61,7\u20138; task.json /criteria/25",
      "repair": "Permit appropriate jurisdictional relief without prejudice and merits relief in the alternative; add credit for jurisdiction analysis."
    }
  ],
  "unverified": [
    "Exact Georgia seller-resale/mitigation rule not independently resolved from a Georgia primary source; do not report C-011 as confirmed."
  ],
  "support_map": {
    "C-001\u2013C-004,C-031\u2013C-034,C-040": "complaint caption and Counts I\u2013IV",
    "C-006\u2013C-010,C-012\u2013C-013,C-018\u2013C-024,C-028\u2013C-030,C-035\u2013C-039": "MSA \u00a7\u00a74\u20137,12\u201313,15\u201316,19; rejection emails; suspension/FM notices; termination notice; POs; BOL; settlement email; complaint",
    "C-015\u2013C-016": "Express MSA/PO relationship supports defense to duplicative unjust-enrichment recovery; pleading in the alternative remains permitted.",
    "C-027": "MSA \u00a711 indemnity/fees provisions give a possible contractual basis; no confirmed defect merely from requesting fees."
  },
  "legal_sources": [
    {
      "url": "https://www.govinfo.gov/content/pkg/USCOURTS-ncmd-1_24-cv-00844/pdf/USCOURTS-ncmd-1_24-cv-00844-0.pdf",
      "point": "Corporation has incorporation and principal-place-of-business citizenship; LLC takes all members citizenship."
    },
    {
      "url": "https://uscode.house.gov/view.xhtml?edition=2022&req=granuleid%3AUSC-2022-title28a-node88",
      "point": "Rule 15 governs amendment; Rule 8 governs responsive pleadings."
    }
  ],
  "source_contradictions": [
    "Complaint \u00b617 says compounded monthly; MSA \u00a77.3 does not. Complaint \u00b618 assigns notice to \u00a712.2; actual MSA puts notice in \u00a712.1. These are opposing allegations to challenge, not automatically task defects."
  ]
}
```
