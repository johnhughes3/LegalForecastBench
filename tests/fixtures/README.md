# Fixtures

Fixture roots are split by artifact type so tests can exercise case packets,
manifests, protocol validation, and end-to-end benchmark workflows
independently. Empty or placeholder fixture directories are documented here
rather than through one-line nested README files.

The shared golden corpus is synthetic and lives in
`legalforecast.testing.golden_fixtures`. Keep reusable edge cases there instead
of inventing local one-off fixtures in each test module. The corpus currently
covers:

- clean full grants and clean denials;
- mixed dispositions;
- leave-to-amend outcomes;
- multiple and grouped defendants;
- ambiguous orders;
- false-positive dismissal docket entries;
- related cases;
- OCR noise;
- malformed model outputs;
- minimal manifest/protocol smoke data.

Directory roles:

- `case_packet/`: reserved for clean pre-decision case-packet fixtures.
- `manifests/`: reserved for manifest fixtures.
- `protocols/`: reserved for protocol fixtures.
- `golden_cases/`: catalog of reusable synthetic legal edge cases.
- `mock_model_outputs/`: catalog of deterministic model-output scenarios.
- `packet_render_ci/`: minimal acquisition export used by the packet-render workflow gate.

See `tests/fixtures/golden_cases/README.md` for fixture IDs and expected uses.

Offline mock-model responses live in
`legalforecast.testing.mock_model_outputs`; see
`tests/fixtures/mock_model_outputs/README.md` for parser, scorer, refusal, and
tool-accounting fixture IDs.
