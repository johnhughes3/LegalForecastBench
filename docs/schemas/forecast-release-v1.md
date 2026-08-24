# `legalforecast.forecast-release.v1`

`forecast-release.v1` is the outcome-blinded public execution manifest. It is canonical artifact JSON: UTF-8, sorted object keys, compact separators, no non-finite numbers, and one trailing newline. `release_digest` is the raw lowercase SHA-256 commitment over the same object with that field omitted.

Cases and prediction units are sorted by ID. Each case has a sorted, globally unique document index whose entries commit a safe relative path, predecision role, byte count, and raw SHA-256. Each unit binds its case, claim identity, non-empty string count label and scoring eligibility, sorted indexes into that case document index, plus the path, byte count, and raw SHA-256 of its packet and prompt. Every document, packet, and prompt has a distinct path so one byte source cannot be assigned multiple semantic roles. Absolute paths, `.` or `..` components, backslashes, outcome-bearing roles, extra fields, duplicates, reordered members, missing cases, and out-of-range indexes are invalid.

The supported issuer is `uv run legalforecast release issue`; the deterministic conformance producer is `uv run legalforecast release issue-synthetic`. Validation is `uv run legalforecast release validate` or `legalforecast.release.load_forecast_execution` when labels must remain inaccessible.
