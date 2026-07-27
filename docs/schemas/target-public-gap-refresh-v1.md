# Exact-target public-gap refresh v1

`plan-target-public-gaps` and `execute-target-public-gaps` form a public-recovery overlay for an already authenticated `project-target-cohort` artifact.
It cannot select new cases or alter the exact target.

Planning reruns the canonical target verifier, checks an external SHA-256 for the target run card, subtracts the authenticated free-download manifest from the selected document set, and commits the resulting gap and docket manifests.
The exact selected-case, document, existing-download, gap, and affected-docket counts are committed in each immutable plan and its manifests rather than fixed by this schema.
The plan independently commits the original target root, run-card and projection-file hashes, semantic projection hash, selection and free-manifest file hashes, ordered selected-candidate hash, selected document-key hash, and the exact ordered required-gap document-ID hash.
Planning is provider-free.
Plan publication revalidates both the caller-visible parent-directory inode and final directory-entry inode through the last read before returning; a parent rename, rebind, or destination swap fails closed.

Execution requires the immutable plan path plus its caller-supplied external SHA-256 and replays the complete target artifact closure before constructing a provider.
Before provider construction it safely creates and opens the final-output parent, cycle-store parent, raw-artifact root, raw-page child, and document root component by component without following links.
The cycle database and lock are exclusively created or opened as unique regular non-symlink children; bound-path SQLite connections open through the pinned database descriptor, and the database directory-entry identity is checked again immediately after connection acquisition and before explicit SQLite pragma or schema writes.
After public discovery and before the document-source provider is constructed, execution creates and pins every exact candidate/provider document directory.
Terminal publication likewise walks or creates the staging tree descriptor-relatively, holds every nested directory descriptor, and writes only relative to those descriptors.
Those bindings remain open through SQLite, raw-page, document, and terminal-tree publication; caller-visible paths must continue to name the pinned inodes at every stage, while runtime writes use the pinned descriptor paths.
The command rejects a fresh Firecrawl cap above 500 and workers above 10; the durable scheduler enforces that immutable cap.
Run evidence sets PACER, RECAP Fetch, document purchase, model calls, evaluation, freeze, and dispatch authority to `false`.

The existing budgeted scheduler fetches only the exact CourtListener docket URLs in the docket manifest.
Pagination stops only after every selected document entry number required for that docket is observed, after proven docket exhaustion, or at the immutable page cap.
A required-entry-only bundle is labeled `required_entries_only`; it is not represented as exhaustive or anchor-window complete.
Missing terminal entries, page-cap exhaustion, contradictory repeated rows, restrictions, private or sealed markers, ambiguous document identity, or an unallowlisted public URL produce document-level exclusion records.

Newly public links pass through the existing public packet planner and `bridge_free_download_requests_from_selection`.
Terminal evidence is a distinct per-document outcome ledger that partitions every required gap exactly once into newly free or terminal gap failure, requires the newly free download manifest to equal the successful outcome set, and commits outcome and newly free manifest hashes with zero purchased documents or purchase activity.
The completed execution tree has a closed seven-artifact shape: four data JSONL artifacts, one summary, one receipt, and one completion log.
The receipt commits the exact four data artifacts plus the summary; the summary independently commits the exact data artifacts and repeats the terminal commitments; and the terminal commitments include the immutable plan SHA-256 and reconcile the plan gap identities, transition/request identities, outcome partition, and newly free download identities.
Resume validates every digest and both commitment layers before any provider is constructed; missing, extra, empty, or inconsistent commitments fail closed.
It is not the canonical per-case exclusion ledger; normal provider-free target reprojection creates any canonical candidate exclusions after merging and clearing the newly free downloads.
This lineage supports an authenticated all-free successor projection; it does not reuse or replace a prior human purchase decision.
The command then uses `download_free_docket_documents`, retaining its allowlisted-host, PDF magic, size ceiling, hash, atomic-write, and resumable-checkpoint checks.
Only positively classified remote content failures (empty, non-PDF, invalid content metadata, or size-ceiling responses) become terminal gap outcomes; checkpoint, preexisting-output, filesystem, and other local invariant failures abort the run.
The output is still acquisition evidence, not packet eligibility.
The existing disclosure-provenance clearance and provider-free target reprojection must consume the augmented manifest before packet planning; this overlay does not call a model, evaluate, freeze, or dispatch.
