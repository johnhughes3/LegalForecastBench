# Golden Cases

The golden corpus is synthetic and public-record-safe. It exists in
`legalforecast.testing.golden_fixtures` so pytest, fixture E2E runs, parser
tests, scoring tests, and future CLI smoke tests can reuse the same cases.

| Fixture ID | Edge Case | Expected Use |
| --- | --- | --- |
| `fixture_clean_grant` | Clean full grant | Happy-path discovery, unitization, labeling, and scoring for a fully dismissed unit. |
| `fixture_clean_denial` | Clean denial | Happy-path scoring for a surviving claim. |
| `fixture_mixed_disposition` | Mixed disposition | Claim-level and unit-level split outcomes. |
| `fixture_leave_to_amend` | Amended complaint / leave to amend | Secondary amendment labels after full dismissal. |
| `fixture_multiple_defendants` | Multiple defendants | Claim-defendant unit splitting. |
| `fixture_grouped_defendants` | Grouped defendants | Claim-defendant-group unit logic and rationale checks. |
| `fixture_ambiguous_order` | Ambiguous order | Review routing or exclusion when the disposition is not reliably mappable. |
| `fixture_false_positive_dismissal` | False-positive dismissal entry | Docket search terms that mention dismissal but are not MTD candidates. |
| `fixture_related_cases` | Related cases | Related-family flags, capped-case sensitivity, and contamination checks. |
| `fixture_ocr_noise` | OCR noise | Extraction normalization and review flags. |
| `fixture_malformed_model_output` | Malformed model output | Parser, invalid-output penalty, and refusal/error accounting tests. |
| `fixture_minimal_protocol` | Minimal protocol / manifest | Freeze/hash and preregistration smoke tests. |

Structured test logs should use the canonical field names exported as
`REQUIRED_PIPELINE_LOG_FIELDS`:

```text
case_id
candidate_id
stage
source_provider
source_document_id
source_hash
decision
exclusion_reason
elapsed_ms
request_count
estimated_cost
```
