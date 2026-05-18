# Tests

Default tests should run offline against synthetic fixtures or recorded public
metadata. Live API tests must stay opt-in so normal development does not require
case.dev credentials or paid model calls.

Reusable golden cases live in `legalforecast.testing.golden_fixtures`; fixture
documentation lives under `tests/fixtures/`. Prefer those builders over local
ad hoc fixtures so ingestion, eligibility, unitization, labeling, harness,
scoring, and reporting tests exercise the same edge cases.
