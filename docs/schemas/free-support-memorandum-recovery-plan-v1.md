# Free support-memorandum recovery plan v1

`legalforecast.free_support_memorandum_recovery_plan.v1` is a provider-free, non-executable plan for the single authenticated Cycle 1 supporting memorandum omitted from candidate `73327542`.

The planner accepts only the path to a persisted `legalforecast.target_raw_docket_auxiliary_provenance_bridge.v1` descriptor and reloads it through the existing bridge authenticator. It derives candidate `73327542`, target ECF 13, supporting ECF 14, the canonical source-document ID, and the unrestricted CourtListener storage URL from the authenticated raw docket. Callers cannot supply or override those values through a constructed bridge object.

The record commits the exact selection, bridge, raw-artifact manifest, raw docket bytes, target/support entry numbers, source identity, document role, description, URL, and linkage basis. Every authority flag for paid retrieval, PACER, RECAP Fetch, model providers, retrieval, parsing, materialization, selection mutation, evaluation, freeze, and dispatch is `false`. Verification reloads the bridge and requires canonical byte-identical rederivation. A separate supported execution path must reauthenticate the plan before it may download or integrate the free document.
