# Corpus split public-history audit and cutover map

This audit supports `legalforecastbench-97nr` and the later `legalforecastbench-2rdw` and `legalforecastbench-g3mo` deletion lanes. It asks the narrow security question that could justify rewriting public Git history and records the package-level boundary for ordinary cutover commits. It does not authorize deletion by itself.

## History review

The inspected public revision is `c53d0738484df9eecdd8f60abe6b70bcd8d5a764`, fetched from `origin/main` on 2026-08-23. The scan covered every object reachable from the repository's refs at that point, not only the checked-out tree.

The review combined a redacted Gitleaks history scan using the installed default rules, an object walk using `git rev-list --objects --all` and `git cat-file`, content-signature checks independent of filename extensions, and bounded manual review of candidate secrets, large blobs, document-like objects, credential/key paths, database/archive paths, and court- or docket-related names. Candidate values were not copied into this report.

No incident-grade removal reason was found. Secret-shaped findings were identifiers, synthetic fixtures, or planted redaction canaries. The valid PDF objects were revisions of the project's public methods preprint; no court filing or PACER/RECAP document was found. Historical user-specific absolute paths were non-access-bearing probe output, not credentials. No private key, live credential, confidential filing, sensitive personal record, or access-bearing path was identified.

This is a heuristic repository audit, not a claim that pattern scanning can prove the absence of every possible secret or determine confidentiality without context. It does not cover commits or refs created after the inspected revision. The deletion lanes must still refresh live references before removing supported code, workflows, environments, or infrastructure.

Decision: preserve public history. If later evidence identifies a real secret or confidential document, rotate or revoke first and open a separate incident-response Bead before considering a history rewrite.

## Cutover map

The disposition applies at package or workflow level. Mixed surfaces such as the CLI and evaluation package must be split along the behavior boundary rather than deleted wholesale.

| Disposition | Public surface | Cutover action and owner |
| --- | --- | --- |
| `KEEP_PUBLIC` | Release contracts and validation; public fixtures; forecast execution; receipt normalization; scoring and reporting; multiharness adapters; shared hashing, canonical serialization, path-safety, and record-validation helpers | `legalforecastbench-j43a` keeps the public CLI limited to fixture, release validation, run, score, report, and retained community commands. Keep the labels release contract and label-consuming scoring boundary, but not private label construction. |
| `KEEP_PUBLIC` | CI, CodeQL, package/release publication, community-harness validation, provider-cell execution, fan-in/publication, and the public evaluation storage/IAM modules under `infra/official-eval*` | `legalforecastbench-j43a` rewires the existing public execution and fan-in workflows to release inputs. Preserve `legalforecastbench-official-eval` and `legalforecastbench-official-eval-fan-in`, with forecast workers unable to read labels or private audit prefixes. |
| `PORT_OR_REIMPLEMENT_PRIVATE` | Discovery, selection, document-need/cost planning, acquisition and authenticated ingest, packet reconstruction, corpus state, unit construction, decision-only labeling, exposure records, and private release issuance | The private importer and factory lanes implement only behavior still required in LegalForecastCorpus, then prove it through the private release and semantic-parity Beads. Historical public manifests are migration evidence, not a runtime protocol to reproduce privately. |
| `PORT_OR_REIMPLEMENT_PRIVATE` | Mixed public CLI handlers and operator scripts for attachment pages, corpus manifests, Stage A replay, packet analysis, and reconstruction | Reimplement supported corpus-operator commands behind the private `lfc` surface. Do not move public run, score, report, fixture, release-validation, or community-harness commands out of LegalForecastBench. |
| `DELETE_AFTER_CUTOVER` | Public ingestion and document-need runtime; purchase, recovery, replacement, and exact-100 successor machinery; Stage A/5.1 issuers; generic freeze and execution-policy machinery; raw Beads observation; lifecycle reconstruction; historical replay helpers and their tests | `legalforecastbench-2rdw` deletes these coherent import clusters only after the private release, semantic parity, public smoke, one-case replacement, legacy tag, supported-command switch, and live-reference audit succeed. Preserve any narrowly necessary legacy read-side behavior at the tag rather than as a supported default-branch import. |
| `DELETE_AFTER_CUTOVER` | Public unitization and labeling pipelines; private-only purchase/provider journals; legacy schemas and staging/export helpers; obsolete dispatch/fan-in code and tests | `legalforecastbench-g3mo` deletes these after private unitization/labels and the public smoke are proven. Retain release labels, scoring, result normalization, reporting, and harness adapters. |
| `DELETE_AFTER_CUTOVER` | `official-paid-labeling*.yaml`, `official-provider-authority-infra.yaml`, `official-s3-access-validation.yaml`, `infra/official-labeling`, and `infra/provider-authority` | `legalforecastbench-g3mo` removes the workflows and Terraform only after `legalforecastbench-j43a` proves zero supported references and the corresponding protected environments can be retired safely. Do not remove shared public evaluation roles or storage still used by forecast execution or fan-in. |
| `ARCHIVE_DOC_ONLY` | Frozen Cycle 1 acquisition, recovery, unitization, labeling, authority, schema, migration, and runbook records that describe the retired implementation | `legalforecastbench-oyzd` preserves the completed boundary in the annotated legacy tag. Later cleanup may remove obsolete records from supported navigation or default-branch docs after live-reference review; Git history and the tag remain the reproduction source. |
| `SECURITY_REVIEW` | None identified in the inspected revision | No incident lane or history rewrite is warranted. Any newly discovered incident-grade material leaves the ordinary deletion path and receives separate response and owner review. |

## Retirement condition

This map is a temporary input to `legalforecastbench-2rdw` and `legalforecastbench-g3mo`. Once both deletion lanes land and remote `main` proves the semantic boundary fences in `legalforecastbench-xvg1`, the map may leave supported documentation; its audit conclusion remains available through Git history and the legacy tag.

No runtime file, workflow, environment, infrastructure resource, branch, tag, or Git object was deleted during this audit.
