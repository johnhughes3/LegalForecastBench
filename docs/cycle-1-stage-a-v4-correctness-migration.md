# Cycle 1 Stage A v4 correctness migration

**Status:** required before Cycle 1 Stage B; governed by [Cycle 1 change control](cycle-1-change-control.md).

## Trigger

The claim-ontology-v2 unitizer accepted multiple `source_document_ids` with one scalar citation excerpt, page, and paragraph. Unit construction then copied that scalar citation payload to every named document without checking the Markdown. An audit of the current 464 raw units found 1,019 citations, of which only 235 matched the named source literally; 608 remained absent after normalization and affected 452 units across 98 candidates. The claim-ontology-v3 structural reviewer also required the model to reproduce literal citation text, causing avoidable reconstruction failures.

The current raw Stage A units, structural flags, merged review queue, proposed translation, and human packet are therefore superseded. They remain immutable historical evidence and must not be patched, rehashed, adjudicated as canonical, or passed to Stage B.

## Versioned successor contract

The successor uses `claim-ontology-v4` for both `llm-unitize` and `llm-review-stage-a`; mixed v4/legacy pairs fail closed.

- Every supplied predecision Markdown document is rendered with stable one-based line selectors.
- Each unitizer citation selects one supplied document and an inclusive range of at most 12 contiguous lines. Local code reconstructs the exact excerpt and page marker.
- Every unit requires at least one operative-complaint citation for claim identity and one target-motion notice or memorandum citation for challenge scope.
- The structural reviewer selects one document-bound line range per flag; it never authors citation text.
- V4 uses a tagged scope object so contradictory `challenge_scope` and `separable_subclaim` states fail reconstruction and receive the existing bounded retry treatment instead of becoming human legal questions.
- Stage A represents purported claims and independently disposable subclaims as pleaded. Lack of a cognizable cause of action is a dismissal ground, not a reason to erase an expressly pleaded and challenged prediction target.

Historical unnamespaced, v2/v2, and v2/v3 chains remain replayable under their exact authenticated contracts. They are not valid predecessors for v4.

## Input corrections included in the successor

The successor cohort must exclude stipulated or voluntary Rule 41 dismissals that were misclassified as contested motions. Strict docket screening now recognizes stipulated-motion and parties'-stipulation formulations, and Stage A independently rejects strong parsed-body evidence that a target-motion role actually contains a stipulated or voluntary dismissal filing before opening a provider client. The cohort must also contain the actual target-motion memorandum: a one-page notice that refers to an absent supporting memorandum is insufficient. Free supporting memoranda discovered in authenticated docket metadata must pass through the normal download, disclosure-clearance, parsing, and lineage checks; if a required memorandum cannot be recovered at zero additional PACER cost, replace that candidate through the supported cohort-successor path.

## Required validation and replay

Before any v4 provider call:

1. Land the versioned code and focused regressions through the one active gate-changing integration lane.
2. Build a supported exact-100 successor selection from authenticated existing and free materials, preserving the complete exclusion ledger and the existing PACER cap.
3. Replay materialization and parsing for every changed candidate and authenticate the complete current chain.
4. Use the frozen Stage A models, provider caps, cycle ID, and canonical provider journal; a new namespace versions the changed contract but does not reset spend authority.

After the v4 unitizer and structural reviewer complete, deterministically verify every citation against its named Markdown document and selected line range, compare candidate and unit matrices with the superseded run, and build a new private human packet. Stage B, evaluation, freeze, and dispatch remain prohibited until the v4 queue is adjudicated and the finalized units replay successfully.
