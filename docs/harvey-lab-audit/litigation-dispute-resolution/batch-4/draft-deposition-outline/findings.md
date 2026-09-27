# Blind rubric audit

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

```json
{
  "task": "draft-deposition-outline",
  "status": "audited",
  "criteria_reviewed": 59,
  "documents_extracted": 12,
  "coverage": "All 59 criteria read. All 12 files extracted, including spreadsheet cells; criterion-bearing passages inspected. Not complete visual review or verification of each case-file allegation.",
  "confirmed_defects": [
    {
      "criteria": [
        "C-008",
        "C-009"
      ],
      "severity": "medium",
      "finding": "The demanded 4:47 PM timestamp conflicts with the actual supplied .eml Date header, Wed, 10 Jan 2024 04:47:00 -0000. That is 04:47 UTC, not 16:47 local; Phoenix conversion places it on the prior evening. The email body does not supply the rubric timestamp. Earlier submission still supports timeliness, but an accurate outline should not be penalized for using actual metadata or flagging discrepancy. Complaint paragraph60 expressly alleges 4:47PM; this is an internal packet contradiction rather than absence of all source support.",
      "source": "q4-risk-report-email.eml Date header; task.json /criteria/7\u20138",
      "repair": "Correct the exhibit header, or accept accurate source-specific timing and a discrepancy note."
    },
    {
      "criteria": [
        "C-054"
      ],
      "severity": "low",
      "finding": "The complaint states 8 of 10 reviews including FY2023 were Exceeds Expectations, but also alleges the FY2023 review was Meets Expectations, as the actual review and spreadsheet confirm. The exact 8-of-10 premise is internally inconsistent in source material and should be attributed/qualified.",
      "source": "first-amended-complaint.docx \u00b612 versus \u00b635; 2023-performance-review.docx; svp-performance-data-2023.xlsx R3",
      "repair": "Accept generally strong prior history without requiring adoption of contradictory exact count."
    }
  ],
  "arguable": [
    {
      "criteria": [
        "C-038"
      ],
      "finding": "Locking in contemporaneous reasons is sound, but the parenthetical suggests it prevents later after-acquired evidence. McKennon permits qualifying later-discovered misconduct to limit remedies. Criterion only demands questioning, so the overstatement is in its rationale, not an inevitably improper examination.",
      "legal_url": "https://www.law.cornell.edu/supct/html/93-1543.ZO.html"
    },
    {
      "criteria": [
        "C-006",
        "C-048",
        "C-049",
        "C-050"
      ],
      "finding": "Mandatory sequencing/leading-question notes and target-admission labels are more specific than the short prompt; useful practice preferences rather than legally necessary elements. A well-organized question outline could be substantively excellent without separately narrating these tactics."
    }
  ],
  "unverified": [],
  "support_map": {
    "C-001\u2013C-007": "Prompt; PIP dates; termination letter; Whitford-Cho email chain",
    "C-010\u2013C-020": "IT service ticket; PIP; spreadsheet rows 3\u20138",
    "C-021\u2013C-030": "Complaint chronology; discrimination complaint email; review/PIP; HR investigation",
    "C-031\u2013C-035": "Complaint \u00b6\u00b680\u201382; personnel file/Yazzie complaint",
    "C-036\u2013C-045": "Termination consultation paragraph; Cho emails; EEO \u00a7\u00a77.4,7.7; questions pursue information rather than assume liability",
    "C-046\u2013C-053": "Prompt and complaint theories, source exhibits, standard outline craft",
    "C-055\u2013C-059": "Cho email chain; spreadsheet K3\u2013K8 (193.5/5 = 38.7); review protest notation; caption; complaint damages"
  },
  "legal_sources": [
    {
      "url": "https://www.law.cornell.edu/supct/html/93-1543.ZO.html",
      "point": "Supreme Court McKennon opinion: after-acquired evidence affects relief, not original discriminatory motive."
    },
    {
      "url": "https://www.law.cornell.edu/supct/html/09-400.ZO.html",
      "point": "Supreme Court Staub opinion: supports exploring biased recommendation and independent investigation, with statute-specific caution."
    },
    {
      "url": "https://supreme.justia.com/cases/federal/us/527/526/",
      "point": "Supreme Court Kolstad opinion: punitive damages concern perceived risk of violating federal rights."
    }
  ],
  "notes": "C-002 fairly permits probing why termination preceded PIP end; PIP expressly reserves earlier termination, so early termination is evidence to examine, not automatic contractual illegality. C-031 complaint pattern is an allegation worth probing, not independently established statistical proof."
}
```
