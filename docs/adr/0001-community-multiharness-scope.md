# ADR 0001: Community multi-harness scope

Status: accepted

PR #7 began as a documentation-only proposal, but its merged scope was substantially larger than the original pull-request description. The merge introduced the non-official community multi-harness implementation: canonical schemas, deterministic selection and execution, host-owned sandbox plans, command and Harvey LAB adapter bridges, conformance checks, community submission packaging and aggregation, static comparison output, release smokes, contributor documentation, and dedicated validation and package-publishing workflows.

The official benchmark remains a separate execution and publication path. Community results are contributor-run and contributor-funded, and the repository validates their artifacts without treating them as official benchmark rows.

This record corrects the historical description drift; it does not change runtime behavior or reopen the removed planning documents.
