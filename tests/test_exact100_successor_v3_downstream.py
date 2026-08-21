"""The v3 cohort root's downstream projection verifier.

Every earlier successor generation shipped a re-verifier that lets the
materialization and parse stages read its cohort root.  v3 shipped none, so a
v3 root is unreadable downstream no matter how well it authenticates itself.
This is that verifier.

It separates two questions that are easy to conflate.  *Authentication* asks
whether the root was produced by the run it claims -- that is a replay, it
recurses to a sealed anchor whose digest is pinned in code, and it is injected
here so the surface below can be exercised without that anchor.  *Publication*
asks whether the bytes on disk are the ones the run card commits, and whether
they can be handed downstream; that is what these tests pin.

Fixtures are synthetic throughout: no corpus candidate, document, digest or
path appears here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion.exact100_successor_v3.downstream import (
    OUTPUT_NAMES,
    AuthenticatedV3Root,
    Exact100SuccessorV3DownstreamError,
    verify_exact100_successor_replacement_v3_projection,
)

_STATE_CARD = "run-cards/project-exact100-successor-replacement-v3.json"
_DOCUMENT = "owner-adjudicated-source/documents/case001/doc-1.pdf"


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()


def _manifest_row(candidate: str, document: str, phase: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate,
        "free_or_purchased": phase,
        "source_document_id": document,
    }


def _payloads() -> dict[str, bytes]:
    selection = _jsonl([{"candidate_id": f"case{index:03d}"} for index in range(100)])
    manifest = _jsonl(
        [
            _manifest_row("case001", "doc-1", "free"),
            _manifest_row("case002", "doc-2", "purchased"),
        ]
    )
    clearance = _jsonl(
        [
            {"candidate_id": "case001", "source_document_id": "doc-1"},
            {"candidate_id": "case002", "source_document_id": "doc-2"},
        ]
    )
    return {
        "target-cohort-selection.jsonl": selection,
        "target-cohort-projection.json": b'{"synthetic": true}\n',
        "case-relevance.jsonl": _jsonl([{"candidate_id": "case001"}]),
        "document-downloads-merged.jsonl": manifest,
        "disclosure-clearance.jsonl": clearance,
        "restriction-evidence.jsonl": _jsonl([{"candidate_id": "case001"}]),
        "core-filter-results.jsonl": _jsonl([{"candidate_id": "case001"}]),
        "successor-terminal-exclusions.jsonl": _jsonl([{"candidate_id": "case003"}]),
        "successor-promotions.jsonl": _jsonl([{"candidate_id": "case001"}]),
        "methods-disclosure.json": b'{"synthetic": true}\n',
    }


def _v3_root(tmp_path: Path, **card_overrides: Any) -> Path:
    root = tmp_path / "59-synthetic-v3"
    payloads = _payloads()
    document_bytes = b"%PDF-1.7 synthetic\n"
    for relative, payload in payloads.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (root / _DOCUMENT).parent.mkdir(parents=True, exist_ok=True)
    (root / _DOCUMENT).write_bytes(document_bytes)

    card: dict[str, Any] = {
        "schema_version": "legalforecast.exact100_successor_replacement_state.v3",
        "stage": "project-exact100-successor-replacement-v3",
        "status": "completed",
        "selected_case_count": 100,
        "output_commitments": {
            **{relative: _sha(payload) for relative, payload in payloads.items()},
            _DOCUMENT: _sha(document_bytes),
        },
    }
    card.update(card_overrides)
    (root / _STATE_CARD).parent.mkdir(parents=True, exist_ok=True)
    (root / _STATE_CARD).write_bytes(json.dumps(card, sort_keys=True).encode() + b"\n")
    return root


def _ok(root: Path) -> AuthenticatedV3Root:
    """A receipt naming the root actually handed to the hook."""

    return AuthenticatedV3Root(root=root)


def _verified(root: Path) -> dict[str, Any]:
    calls: list[Path] = []

    def authenticate(target: Path) -> AuthenticatedV3Root:
        calls.append(target)
        return AuthenticatedV3Root(root=target)

    result = verify_exact100_successor_replacement_v3_projection(
        root, authenticate=authenticate
    )
    assert calls == [root], "the root must be authenticated, not merely read"
    return result


def test_a_complete_v3_root_publishes_the_downstream_surface(tmp_path: Path) -> None:
    verified = _verified(_v3_root(tmp_path))

    assert verified["run_card_path"].name.endswith(".json")
    assert len(verified["selection_records"]) == 100
    assert verified["selected_document_keys"] == {
        ("case001", "doc-1"),
        ("case002", "doc-2"),
    }


def test_the_merged_manifest_is_split_by_phase(tmp_path: Path) -> None:
    """Downstream consumes free and purchased separately; v3 stores them merged."""

    verified = _verified(_v3_root(tmp_path))

    assert [row["candidate_id"] for row in verified["free_manifest"]] == ["case001"]
    assert [row["candidate_id"] for row in verified["purchased_manifest"]] == [
        "case002"
    ]
    assert [row["candidate_id"] for row in verified["free_clearance"]] == ["case001"]
    assert [row["candidate_id"] for row in verified["purchased_clearance"]] == [
        "case002"
    ]


def test_every_declared_output_is_published_as_verified_bytes(tmp_path: Path) -> None:
    """Downstream reads bytes from here, not from the filesystem again."""

    root = _v3_root(tmp_path)
    verified = _verified(root)
    published = verified["verified_artifact_bytes"]

    assert set(published) == {
        *(str((root / relative).absolute()) for relative in OUTPUT_NAMES.values()),
        str((root / _DOCUMENT).absolute()),
    }
    assert published[str((root / _STATE_CARD).absolute())] == (
        (root / _STATE_CARD).read_bytes()
    )
    assert verified["selection_bytes"] == _payloads()["target-cohort-selection.jsonl"]


def test_the_published_output_map_matches_the_emitter(tmp_path: Path) -> None:
    """The commitments are keyed on the emitter's map, so the two must agree.

    They are separate copies on purpose -- the verifier must not import the
    emitter's CLI -- which is exactly why a drift between them needs a test.
    """

    from legalforecast.ingestion.exact100_successor_v3.cli import _OUTPUT_NAMES

    assert dict(OUTPUT_NAMES) == dict(_OUTPUT_NAMES)


def test_a_root_without_the_v3_state_card_refuses(tmp_path: Path) -> None:
    root = _v3_root(tmp_path)
    (root / _STATE_CARD).unlink()

    with pytest.raises(Exact100SuccessorV3DownstreamError, match="carries no v3"):
        verify_exact100_successor_replacement_v3_projection(
            root, authenticate=lambda root: AuthenticatedV3Root(root=root)
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "dry_run"),
        ("stage", "something-else"),
        ("schema_version", "legalforecast.exact100_successor_replacement_state.v2"),
        ("selected_case_count", 99),
    ],
)
def test_a_card_that_is_not_a_completed_v3_projection_refuses(
    tmp_path: Path, field: str, value: Any
) -> None:
    root = _v3_root(tmp_path, **{field: value})

    with pytest.raises(Exact100SuccessorV3DownstreamError, match="not a completed"):
        verify_exact100_successor_replacement_v3_projection(root, authenticate=_ok)


def test_an_output_that_differs_from_its_commitment_refuses(tmp_path: Path) -> None:
    root = _v3_root(tmp_path)
    (root / "target-cohort-selection.jsonl").write_bytes(b"tampered\n")

    with pytest.raises(Exact100SuccessorV3DownstreamError, match="differs from"):
        verify_exact100_successor_replacement_v3_projection(root, authenticate=_ok)


def test_an_owner_adjudicated_document_that_differs_refuses(tmp_path: Path) -> None:
    """The promoted documents are the evidence the promotion rests on.

    They sit outside the cohort surface files, so a verifier that checked only
    those would report a root whose purchased PDFs had been replaced as sound.
    """

    root = _v3_root(tmp_path)
    (root / _DOCUMENT).write_bytes(b"%PDF-1.7 substituted\n")

    with pytest.raises(Exact100SuccessorV3DownstreamError, match="differs from"):
        verify_exact100_successor_replacement_v3_projection(root, authenticate=_ok)


def test_a_missing_committed_document_refuses(tmp_path: Path) -> None:
    root = _v3_root(tmp_path)
    (root / _DOCUMENT).unlink()

    with pytest.raises(Exact100SuccessorV3DownstreamError, match="is missing"):
        verify_exact100_successor_replacement_v3_projection(root, authenticate=_ok)


def test_a_manifest_row_of_an_unknown_phase_refuses(tmp_path: Path) -> None:
    """A row that is neither free nor purchased would vanish from both splits."""

    root = _v3_root(tmp_path)
    payloads = _payloads()
    payloads["document-downloads-merged.jsonl"] = _jsonl(
        [_manifest_row("case001", "doc-1", "gifted")]
    )
    (root / "document-downloads-merged.jsonl").write_bytes(
        payloads["document-downloads-merged.jsonl"]
    )
    card = json.loads((root / _STATE_CARD).read_text())
    card["output_commitments"]["document-downloads-merged.jsonl"] = _sha(
        payloads["document-downloads-merged.jsonl"]
    )
    (root / _STATE_CARD).write_bytes(json.dumps(card, sort_keys=True).encode() + b"\n")

    with pytest.raises(Exact100SuccessorV3DownstreamError, match="invalid phase"):
        verify_exact100_successor_replacement_v3_projection(root, authenticate=_ok)


def test_authentication_failure_is_not_swallowed(tmp_path: Path) -> None:
    """Publication must never proceed on a root that failed its replay."""

    def refuse(_root: Path) -> None:
        raise ValueError("replay differs")

    with pytest.raises(ValueError, match="replay differs"):
        verify_exact100_successor_replacement_v3_projection(
            _v3_root(tmp_path), authenticate=refuse
        )


def test_a_callable_that_does_not_authenticate_cannot_publish(tmp_path: Path) -> None:
    """The injected replay must prove it ran, not merely be callable.

    An unconstrained hook takes a no-op happily: it type-checks, every test
    passes, and publication proceeds on a root nothing replayed. So the hook
    returns a receipt naming the root it authenticated, and a receipt for some
    other root -- or none at all -- refuses.
    """

    root = _v3_root(tmp_path)

    with pytest.raises(
        Exact100SuccessorV3DownstreamError, match="did not authenticate"
    ):
        verify_exact100_successor_replacement_v3_projection(
            root, authenticate=lambda _root: None
        )


def test_a_receipt_for_another_root_refuses(tmp_path: Path) -> None:
    root = _v3_root(tmp_path)
    other = tmp_path / "some-other-root"

    with pytest.raises(
        Exact100SuccessorV3DownstreamError, match="did not authenticate"
    ):
        verify_exact100_successor_replacement_v3_projection(
            root, authenticate=lambda _root: AuthenticatedV3Root(root=other)
        )
