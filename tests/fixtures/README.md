# Fixtures

Fixture roots are split by artifact type so tests can exercise case packets, manifests, freeze validation, and end-to-end benchmark workflows independently. Empty or placeholder fixture directories are documented here rather than through one-line nested README files.

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
- minimal manifest/freeze smoke data.

Directory roles:

- `case_packet/`: reserved for clean pre-decision case-packet fixtures.
- `manifests/`: reserved for manifest fixtures.
- `golden_cases/`: catalog of reusable synthetic legal edge cases.
- `mock_model_outputs/`: catalog of deterministic model-output scenarios.
- `packet_render_ci/`: deterministic production packet-builder input plus independently reviewed exact-output and SHA-256 goldens used by the packet-render workflow gate.
- Future `claude_native_containment/` (directory intentionally absent until evidence approval): reserved for the independently reviewed Claude Code 2.1.218 host-specific containment receipt. The intended full path is `tests/fixtures/claude_native_containment/claude-code-native-containment-2.1.218.json`; no fixture or passing containment evidence is committed. See the [containment feasibility record](../../docs/adapters/claude-code-native-containment.md).

See `tests/fixtures/golden_cases/README.md` for fixture IDs and expected uses.

Offline mock-model responses live in
`legalforecast.testing.mock_model_outputs`; see
`tests/fixtures/mock_model_outputs/README.md` for parser, scorer, refusal, and
tool-accounting fixture IDs.

## Packet-render golden provenance

`packet_render_ci/packet-build-input.jsonl` is a synthetic, timestamp-fixed production acquisition input. `expected-packets.jsonl` is the byte-for-byte reviewed output of `legalforecast acquisition build-packets`; `expected-packet-render.json` independently freezes its SHA-256 for `reconstruct_packets --verify-packet-render-dir`. The compared packet contains no runtime timestamp, temporary path, UUID, or platform-dependent field.

Verify the production builder against the reviewed golden with:

```bash
uv run pytest -q \
  tests/test_packet_render_ci_workflow.py::test_production_packet_builder_matches_reviewed_golden
```

The focused test supplies exact authenticated fixture lineage while the target-100 materializer E2E independently exercises full source-chain replay. To retain a changed candidate for review, rerun the focused test with `--basetemp tmp/packet-render-golden-review`; its generated `packet-render/packets.jsonl` remains below that directory even when the golden assertion fails.

An intentional builder change requires reviewing the complete diff, replacing `expected-packets.jsonl`, and updating `packet_sha256` in `expected-packet-render.json` in the same commit. CI only generates an actual packet and compares it with these checked-in expectations; it must never update either golden.
