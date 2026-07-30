# Canonical sealed deliverables

`legalforecast.multiharness.deliverable_manifest.v1` is the harness-independent boundary between a solver run and later evaluation.

Each harness declares a `DeliverableArtifactProjection` for every allowed output.
The projection maps a harness-specific source path to a canonical path and declares the artifact ID, media type, and maximum byte size.
Source paths are discovery instructions only and never enter the canonical manifest, so equivalent Claude, Codex, and native outputs produce identical manifest records.

`seal_deliverable` requires the source tree to contain exactly the declared regular, single-link files and their necessary parent directories.
It rejects missing files, extra files or directories, symlinks, hard links, unsafe or percent-encoded paths, duplicate case-folded paths, invalid media types, and per-file, aggregate, or file-count limit violations.
It copies verified bytes into a fresh canonical root and makes every file and directory read-only.

The manifest binds:

- the canonical task, run, and configuration SHA-256 commitments;
- every allowed canonical path and declared media type;
- every file's SHA-256, observed size, and maximum size;
- the observed and maximum aggregate size;
- the complete sealed-tree commitment, including directories; and
- a deterministic commitment to the manifest itself.

`validate_sealed_deliverable` requires the exact schema, revalidates the manifest commitment, rejects writable or structurally unsafe trees, recomputes the complete tree commitment, and streams every declared file to verify its hash and size.
Contributor files remain opaque bytes: sealing and validation do not import, parse, render, invoke, or execute their content.

The source root, destination parent, fresh sealed root, and the interval from final validation to read-only evaluator mounting require exclusive coordination from other same-UID processes.
Read-only filesystem modes are integrity hygiene, not a same-UID isolation boundary.

This contract is intentionally a foundation surface.
Runner, container, native-adapter, and evaluator wiring belongs to the downstream runtime and evaluator beads.
