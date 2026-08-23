# Exact-100 zero-cost recovery terminal authority v3

`legalforecast.exact100_zero_cost_recovery_terminal_authority.v3` is an in-process proof that a fresh canonical CourtListener observation was a terminal 404 for one exact selected tuple. It is not a persisted artifact. A caller-owned recovery bundle cannot mint it, and recovery-command resume cannot recreate it.

The proof binds:

- the predecessor selection digest
- the recovery-request digest
- candidate, source document, document role, CourtListener docket, and docket entry
- `recovery_mode=courtlistener_rest_noncharging_only`
- `terminal_status=unavailable`
- `observation_status_code=404`

It does not bind the raw 404 response bytes. The v1/v2 persisted request, receipt, run card, REST observation, transcript, and `rest-observation-response.bin` remain the reproducible output commitments. Successor replay still validates that closed v2 bundle, then requires a sealed live producer capability whose selection and request commitments match it. A semantically equivalent 404 body may differ from the saved sidecar. A fresh public-document or other nonterminal result still fails closed.

The earlier complete evidence-commitment-map equality check, including 404 body bytes, remains the v2 authorize boundary. v3 does not reinterpret or accept v1 recovery artifacts.
