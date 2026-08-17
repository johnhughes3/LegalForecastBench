"""Offline fixtures for the replay-spec issuer and authorization recorder.

Every artifact here is hand-authored (``synthetic: true``); none was produced by
a production command.  The predecessor run cards mimic only the fields the
issuer derives from, and the throwaway SSH key exists so the detached-signature
path can be exercised without the owner's key.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    ISSUANCE_REQUEST_SCHEMA_VERSION,
)

SYNTHETIC_PRINCIPAL = "issuer-fixture@example.invalid"
REGISTRY_SHA256 = "a" * 64
CAPS_SHA256 = "b" * 64
UNITIZER_ENTRY_SHA256 = "c" * 64
REVIEWER_ENTRY_SHA256 = "d" * 64
ROOT_IDENTITY_SHA256 = "e" * 64
EXPECTED_RECEIPT_SHA256 = "f" * 64
CANDIDATE_IDS = ("cand-a", "cand-b")


def build_issuance_inputs(
    root: Path,
    *,
    per_candidate_ceiling: str = "6.00",
    hard_ceiling: str = "12.00",
    estimated_cost: str = "6.00",
    unitizer_reservation: str = "2.00",
    reviewer_reservation: str = "1.00",
    candidate_ids: tuple[str, ...] = CANDIDATE_IDS,
) -> Path:
    """Write synthetic predecessor cards, artifacts, and an issuance request."""

    inputs = root / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    for name in (
        "prediction-units.jsonl",
        "unitization-audit.jsonl",
        "unitization-review-queue.jsonl",
        "structural-flags.jsonl",
        "structural-review-audit.jsonl",
        "review-queue-reviewed.jsonl",
        "model-registry.json",
        "provider-caps.json",
        "finalized.jsonl",
        "adjudications.jsonl",
        "apply-card.json",
        "selection.jsonl",
        "selection-card.json",
        "download.jsonl",
        "clearance.jsonl",
        "materialization-card.json",
        "parse-requests.jsonl",
        "parser-manifest.jsonl",
        "parser-card.json",
        "cycle-index.json",
        "acquired-documents.json",
        "repair-manifest.json",
        "repair-approval.json",
        "snapshot-manifest.json",
        "source-lineage.json",
        "repair-execution.json",
        "repair-receipt.json",
        "provider.sqlite3",
        "request.md",
    ):
        (inputs / name).write_bytes(f"synthetic {name}\n".encode())
    for name in ("documents", "markdown", "snapshots"):
        (inputs / name).mkdir(exist_ok=True)

    unitize_card = inputs / "llm-unitize.json"
    unitize_card.write_bytes(
        _canonical(
            {
                "synthetic": True,
                "lineage_roots": {
                    "provider_journal": str(inputs / "provider.sqlite3"),
                },
                "model_execution": {
                    "model_key": "fixture:unitizer",
                    "model_entry_sha256": f"sha256:{UNITIZER_ENTRY_SHA256}",
                    "model_registry_sha256": REGISTRY_SHA256,
                    "provider_attempt_namespace": "claim-ontology-v5",
                },
                "output_commitments": {
                    "prediction_units": _commitment(inputs / "prediction-units.jsonl"),
                    "llm_unitization_audit": _commitment(
                        inputs / "unitization-audit.jsonl"
                    ),
                    "unitization_review_queue": _commitment(
                        inputs / "unitization-review-queue.jsonl"
                    ),
                },
            }
        )
    )
    review_card = inputs / "llm-review-stage-a.json"
    review_card.write_bytes(
        _canonical(
            {
                "synthetic": True,
                "model_execution": {
                    "model_key": "fixture:reviewer",
                    "model_entry_sha256": f"sha256:{REVIEWER_ENTRY_SHA256}",
                    "model_registry_sha256": REGISTRY_SHA256,
                    "provider_attempt_namespace": "claim-ontology-v4",
                },
                "source_commitments": {
                    "model_registry": _commitment(
                        inputs / "model-registry.json", sha256=REGISTRY_SHA256
                    ),
                    "provider_cycle_caps": _commitment(
                        inputs / "provider-caps.json", sha256=CAPS_SHA256
                    ),
                },
                "output_commitments": {
                    "structural_flags": _commitment(inputs / "structural-flags.jsonl"),
                    "audit": _commitment(inputs / "structural-review-audit.jsonl"),
                    "review_queue": _commitment(inputs / "review-queue-reviewed.jsonl"),
                },
            }
        )
    )

    request_path = root / "issuance-request.json"
    request_path.write_bytes(
        _canonical(
            {
                "schema_version": ISSUANCE_REQUEST_SCHEMA_VERSION,
                "cycle_id": "cycle-fixture",
                "lineage_index_path": str(inputs / "cycle-index.json"),
                "active_root_identity_sha256": ROOT_IDENTITY_SHA256,
                "predecessor": {
                    "unitization_run_card_path": str(unitize_card),
                    "structural_review_run_card_path": str(review_card),
                    "finalized_prediction_units_path": str(inputs / "finalized.jsonl"),
                    "adjudications_path": str(inputs / "adjudications.jsonl"),
                    "apply_unitization_run_card_path": str(inputs / "apply-card.json"),
                    "controlled_private_root": None,
                    "initialization_receipt_path": None,
                },
                "successor": {
                    "selection_path": str(inputs / "selection.jsonl"),
                    "selection_run_card_path": str(inputs / "selection-card.json"),
                    "download_manifest_path": str(inputs / "download.jsonl"),
                    "disclosure_clearance_path": str(inputs / "clearance.jsonl"),
                    "materialization_run_card_path": str(
                        inputs / "materialization-card.json"
                    ),
                    "document_root": str(inputs / "documents"),
                    "parse_requests_path": str(inputs / "parse-requests.jsonl"),
                    "parser_manifest_path": str(inputs / "parser-manifest.jsonl"),
                    "parser_run_card_path": str(inputs / "parser-card.json"),
                    "markdown_root": str(inputs / "markdown"),
                    "controlled_private_root": None,
                    "initialization_receipt_path": None,
                },
                "repair_receipt": {
                    "acquired_documents_path": str(inputs / "acquired-documents.json"),
                    "manifest_path": str(inputs / "repair-manifest.json"),
                    "approval_path": str(inputs / "repair-approval.json"),
                    "snapshot_manifest_path": str(inputs / "snapshot-manifest.json"),
                    "source_lineage_path": str(inputs / "source-lineage.json"),
                    "snapshots_root": str(inputs / "snapshots"),
                    "execution_path": str(inputs / "repair-execution.json"),
                    "receipt_path": str(inputs / "repair-receipt.json"),
                    "expected_receipt_sha256": EXPECTED_RECEIPT_SHA256,
                },
                "provider_accounts": {"fixture": "fixture-account"},
                "candidate_ids": list(candidate_ids),
                "spend": {
                    "estimated_cost_usd": estimated_cost,
                    "hard_ceiling_usd": hard_ceiling,
                    "per_candidate_ceiling_usd": per_candidate_ceiling,
                    "invocation_reservations_usd": {
                        "unitizer": unitizer_reservation,
                        "reviewer": reviewer_reservation,
                    },
                },
                "outputs_root": str(root / "outputs"),
            }
        )
    )
    return request_path


def build_signing_checkout(root: Path) -> tuple[Path, Path, str]:
    """Create a clean Git checkout whose allowed-signers trusts a throwaway key.

    Returns the checkout root, the private key path, and the checkout's HEAD
    commit.  The key never leaves ``tmp_path`` and is unrelated to any real
    signing identity; the commit exists because the executor binds a clean
    runtime checkout commit into every invocation.
    """

    checkout = root / "checkout"
    checkout.mkdir(parents=True, exist_ok=True)
    key = root / "signing-key"
    subprocess.run(
        [
            "ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            "issuer-fixture",
            "-f",
            str(key),
        ],
        check=True,
        capture_output=True,
    )
    allowed = root / "allowed-signers"
    fields = key.with_suffix(".pub").read_text(encoding="utf-8").strip().split()
    allowed.write_text(
        f"{SYNTHETIC_PRINCIPAL} {fields[0]} {fields[1]}\n", encoding="utf-8"
    )
    _git(checkout, "init", "--quiet")
    for name, value in (
        ("gpg.ssh.allowedSignersFile", str(allowed)),
        ("user.signingkey", str(key)),
        ("user.name", "Issuer Fixture"),
        ("user.email", SYNTHETIC_PRINCIPAL),
        ("commit.gpgsign", "false"),
    ):
        _git(checkout, "config", name, value)
    (checkout / "README.md").write_text("issuer fixture checkout\n", encoding="utf-8")
    _git(checkout, "add", "README.md")
    _git(checkout, "commit", "--quiet", "--message", "issuer fixture")
    head = _git(checkout, "rev-parse", "HEAD").stdout.strip()
    return checkout, key, head


def read_json(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True
    )


def _commitment(path: Path, *, sha256: str | None = None) -> dict[str, object]:
    return {"path": str(path), "sha256": f"sha256:{sha256 or ('1' * 64)}"}


def _canonical(value: object) -> bytes:
    return ARTIFACT_CANONICAL_JSON_V1.encode(value)
