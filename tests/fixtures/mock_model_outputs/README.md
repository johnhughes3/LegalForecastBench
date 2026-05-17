# Mock Model Outputs

These fixtures define deterministic raw model responses for offline harness,
parser, scorer, accounting, and leaderboard tests. They are synthetic and should
flow through the same code paths used for real model outputs.

| Fixture ID | Scenario | Expected use |
| --- | --- | --- |
| `mock_calibrated_predictions` | Calibrated predictions | Happy-path parser and scorer fixture. |
| `mock_overconfident_predictions` | Overconfident predictions | Calibration, log-loss, and Brier-sensitivity tests. |
| `mock_always_base_rate_predictions` | Base-rate predictions | Baseline and Brier Skill Score tests. |
| `mock_invalid_json_truncated` | Invalid JSON | Deterministic repair or invalid-output path. |
| `mock_missing_unit_prediction` | Missing unit | Missing-prediction penalty or default-probability path. |
| `mock_duplicate_unit_prediction` | Duplicate unit | Deterministic duplicate-resolution or invalid-output path. |
| `mock_out_of_range_probability` | Out-of-range probability | Strict probability validation path. |
| `mock_refusal_plain_text` | Refusal | Refusal/content-filter accounting path. |
| `mock_tool_abuse_unauthorized_search` | Tool abuse | Tool-call policy and cost accounting path. |

The source of truth is `legalforecast.testing.mock_model_outputs`; this
directory documents the available IDs so future JSONL or cassette exports can
use the same names.
