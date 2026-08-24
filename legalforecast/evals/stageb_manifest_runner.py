"""Additive Cycle 1 Stage B runner for the authenticated manifest input pair.

The historical ``llm-unitize`` run-card is unavailable for the current Stage51
proposal.  This module is intentionally a narrow adapter: it authenticates the
owner-pinned raw unit bytes, derives an in-memory finalized-shaped view only for
the existing Stage B validators, and then delegates prompt construction,
response validation, and provider journaling to ``llm_pipeline``.  It never
changes the legacy acquisition command or publishes a finalized Stage-A
artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts.commitments import (
    ARTIFACT_PREFIXED_SHA256_V1,
    RAW_BYTES_RAW_SHA256_V1,
)
from legalforecast.contracts.schemas import (
    STAGE_B_FROZEN_UNIT_EXCLUSION_ADJUDICATION_INDEX_V1 as _INDEX_SCHEMA,
)
from legalforecast.contracts.schemas import (
    STAGE_B_FROZEN_UNIT_EXCLUSION_ADJUDICATION_V1 as _ADJ_SCHEMA,
)
from legalforecast.contracts.schemas import (
    STAGE_B_MANIFEST_DECISION_TEXTS_RUN_V1,
    STAGE_B_MANIFEST_DECISION_TEXTS_V1,
    STAGE_B_MANIFEST_MERGE_RUN_CARD_V1,
    STAGE_B_MANIFEST_PLAN_V1,
    STAGE_B_MANIFEST_PROVIDER_RESULT_V1,
    STAGE_B_MANIFEST_PROVIDER_SHARD_RUN_CARD_V1,
)
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    load_model_registry,
)
from legalforecast.evals.provider_spend_attempt_handler import (
    conservative_reservation_microusd,
)
from legalforecast.evals.provider_spend_control import (
    AdditionalAttemptPermit,
    FrozenAttemptPolicy,
    ProviderSpendAuthority,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)
from legalforecast.ingestion.decision_text_artifact import (
    SCHEMA_VERSION as DECISION_TEXT_SCHEMA_VERSION,
)
from legalforecast.ingestion.decision_text_artifact import (
    VerifiedDecisionTextArtifact,
)
from legalforecast.labeling.llm_pipeline import (
    FrozenUnitWorkflowRequiredError,
    _frozen_unit_workflow_audit_fields,  # pyright: ignore[reportPrivateUsage]
    _labeling_prompt,  # pyright: ignore[reportPrivateUsage]
    _llm_label_one_model,  # pyright: ignore[reportPrivateUsage]
    _outcome_label,  # pyright: ignore[reportPrivateUsage]
    _prediction_units_by_candidate,  # pyright: ignore[reportPrivateUsage]
    _provider_attempt_journal,  # pyright: ignore[reportPrivateUsage]
    _required_str,  # pyright: ignore[reportPrivateUsage]
    _verified_stage_b_decisions,  # pyright: ignore[reportPrivateUsage]
    lawyer_review_queue_records,
    merge_llm_label_provider_shards,
)
from legalforecast.labeling.provider_journal import (
    ProviderJournalError,
    ReconstructionFailureEvidence,
    provider_prompt_logical_call_scope,
)
from legalforecast.unitization.review import (
    LEGACY_FINALIZED_SCHEMA_VERSION,
    canonical_records_sha256,
    canonical_sha256,
)

JsonRecord = dict[str, Any]

RAW_UNITS_SHA256 = "9bfe41369e50f1dd110ca1d214a9413c6afa60b2f655175e2463796c3d06502a"
DECISION_TEXTS_SHA256 = (
    "01fc5d325b45677ce1f67db1eb1b958ebc9af53d75a7bb496c95b387525a44d7"
)
CURRENT_SELECTION_SHA256 = (
    "ff94024b60fd976edace2bcea0ffc28923651fd0ae36859e6b654e526730dfee"
)
STAGE_B_REGISTRY_SHA256 = (
    "5243b74bfdb2d3accc1a301f7c997b9520abc8586bbf944e22f67e2b263106a2"
)
SPEND_APPROVAL = (
    "I approve up to USD 300 of provider spend for the Cycle 1 Stage B label run, "
    "estimated USD 15, across GPT-5.4 mini and Gemini 3.5 Flash."
)
BEAD_ID = "legalforecastbench-3ak.38.18"
TERMINAL_APPROVAL_BEAD_ID = "legalforecastbench-3ak.38"
TERMINAL_PACKET_APPROVAL = (
    "stage51-terminal-units: approved — packet "
    "8617ee835c3578042a1081f484d6520de187c5da8367e1e6a71228262266dcca"
)
OWNER_CAP_USD = 300.0
EXPECTED_CASE_COUNT = 100
EXPECTED_UNIT_COUNT = 425
MODEL_KEYS = (
    "openai:gpt-5.4-mini-2026-03-17",
    "google:gemini-3.5-flash",
)
PROVIDER_CAP_USD = {"openai": 80.0, "google": 220.0}
PROVIDER_KEY_ENV_NAMES = frozenset(
    {"OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"}
)
OWNER_AUTHOR_ENV = "LEGALFORECAST_OWNER_AUTHOR"
FROZEN_UNIT_ADJUDICATION_INDEX_V1 = str(_INDEX_SCHEMA)
CONTEXTUAL_OWNER_APPROVAL_COMMENT_ID = "b7f63c90-ca42-5a04-8590-4181be613ec1"
CONTEXTUAL_OWNER_APPROVAL_TEXT_SHA256 = (
    "sha256:57c925c08da5dbe25007cc27b1532d8912c61d97702d633091a723efc5f2b7a2"
)
CONTEXTUAL_OWNER_APPROVAL_CANDIDATE_SHA256 = (
    "sha256:119293da5aeb7f9eeb328b041b53026f4322cd619e6bb3604ad6be1a19171d18"
)
CONTEXTUAL_OWNER_APPROVAL_MISSING_UNIT_SHA256 = (
    "sha256:938d24db5ec4977e95abe92aad30b2fea018786d76a6fbc18e10df5930238fa2"
)
ADDITIONAL_ATTEMPT_APPROVAL_COMMENT_ID = "4dee40a6-efe9-57f8-9945-795b167e8591"
ADDITIONAL_ATTEMPT_APPROVAL_TEXT = (
    "2026-08-24 owner ruling: Stage B supporting-excerpt validation should not "
    "block an otherwise valid document label. Add exactly one same-model repair "
    "opportunity containing the validation failure and original submission; if "
    "repair still cannot map supporting evidence, preserve structurally valid "
    "labels and mark evidence unresolved/advisory. Invalid labels remain terminal. "
    "Fastest Cycle 1 path: land current narrow provider-free recovery, resume "
    "shards now, implement generalized repair without holding the run."
)
ADDITIONAL_ATTEMPT_MAX_TOTAL = 2
ADDITIONAL_ATTEMPT_FAILURE_TYPE = "LlmResponseValidationError"
ADDITIONAL_ATTEMPT_FAILURE_MESSAGE = (
    "supporting_excerpt does not appear in decision text"
)
SUPPORTING_EVIDENCE_SIDECAR_KIND = "stage_b_supporting_evidence_sidecar"
SUPPORTING_EVIDENCE_SIDECAR_FIELDS = frozenset(
    {
        "supporting_evidence_status",
        "supporting_evidence_affected_unit_ids",
    }
)

# The replacement rows are not covered by the retired decision-text artifact.
# These source-byte commitments are the authenticated bridge for the exact five
# replacements named by the pinned selection.  Paths remain private metadata.
REPLACEMENT_SOURCE_COMMITMENTS: Mapping[str, Mapping[str, str]] = {
    "488531646": {
        "metadata_sha256": (
            "174630d2fab27d7150fcd551989f9e4951695011e0a385258eaac5870ee5e874"
        ),
        "markdown_sha256": (
            "1bab49a15eb1b9bc9ce0b059aa1aed30eaf5086c2baa8d26ab5fda2747c5281c"
        ),
        "source_sha256": (
            "c9709e664af298b22723301eeaa3566967832e3092427414556d449112cefdc0"
        ),
    },
    "487640333": {
        "metadata_sha256": (
            "0eada30b8ca393ba76116599e287977ad2d7d09a4ed832f4a856ee525bba5a92"
        ),
        "markdown_sha256": (
            "710db830a0295b58de520d6a8af3b9bbb32b755f40c48a612c88e976567a3d39"
        ),
        "source_sha256": (
            "b4110d352a2b1d892513f4228c9f84015b50a0398475d7f9c5cce8fb1c11f026"
        ),
    },
    "487488505": {
        "metadata_sha256": (
            "fe791d4f9287f8afcd9efca3987c97f2be5fe27a0018507396eadb37faeb31fb"
        ),
        "markdown_sha256": (
            "f4eafc023654fd6b1743d5f6c62f488e9055fe104d90c5d67739637895f4d57b"
        ),
        "source_sha256": (
            "ece519302f1e9fd67e9baa918b883239a0038aad2a7410df0f5105811682b825"
        ),
    },
    "488276235": {
        "metadata_sha256": (
            "fe76c02ce86f9224f3da326600790f8e85ce87bb214a9dbced913a47c7f352cc"
        ),
        "markdown_sha256": (
            "dc62d2321ac19ab7de76e36af2e0f49af42f298c06382d46681d0526d328363d"
        ),
        "source_sha256": (
            "cc559efe1c81ccbf045f2883fd674a39839b52f6e3b053027b5199d4ff0d9095"
        ),
    },
    "484932730": {
        "metadata_sha256": (
            "54ffa8b69512ff0ae70b59f3a2b1f20d7dddfb0546616784a32d7991f5562fdc"
        ),
        "markdown_sha256": (
            "b7bee3b02b9a5f04c6227a82a447c8dcb4f73a1f45a2b8ea5bb35467733bd8d2"
        ),
        "source_sha256": (
            "41566313f5082c6ba3da20ca73a6dd34916fa19e676b8a732b8181e454b31c28"
        ),
    },
}


class StageBManifestError(ValueError):
    """Raised when the owner-pinned manifest inputs are not exact."""


def _raw_sha256(payload: bytes) -> str:
    return str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            payload,
            domain=STAGE_B_MANIFEST_PROVIDER_RESULT_V1,
        ).digest
    )


def _owner_author() -> str:
    configured = os.environ.get(OWNER_AUTHOR_ENV, "").strip()
    if configured:
        return configured
    try:
        completed = subprocess.run(
            ["git", "config", "user.name"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise StageBManifestError(
            f"could not resolve owner author from {OWNER_AUTHOR_ENV} or git metadata"
        ) from exc
    author = completed.stdout.strip()
    if not author:
        raise StageBManifestError(
            f"owner author is empty; set {OWNER_AUTHOR_ENV} or git user.name"
        )
    return author


def _validate_provider_environment(provider: str) -> None:
    normalized = provider.strip().lower()
    expected = {
        "openai": "OPENAI_API_KEY",
        "google": "GEMINI_API_KEY",
    }.get(normalized)
    if expected is None:
        raise StageBManifestError(f"unsupported execution provider: {provider}")
    present = sorted(
        name for name in PROVIDER_KEY_ENV_NAMES if os.environ.get(name, "").strip()
    )
    if present != [expected]:
        raise StageBManifestError(
            f"{normalized} execution requires only {expected} among provider keys"
        )


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StageBManifestError(f"{label} must be a regular non-symlink file: {path}")
    return path.read_bytes()


def _jsonl(payload: bytes, label: str) -> tuple[JsonRecord, ...]:
    records: list[JsonRecord] = []
    for line_number, line in enumerate(payload.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StageBManifestError(
                f"{label} has invalid JSON at line {line_number}"
            ) from exc
        if not isinstance(value, Mapping):
            raise StageBManifestError(f"{label} line {line_number} is not an object")
        records.append(dict(cast(Mapping[str, object], value)))
    return tuple(records)


def _issue_frozen_unit_adjudication(
    *,
    output_path: Path,
    owner_comment_id: str,
    provider: str,
    output_root: Path,
    artifact: VerifiedDecisionTextArtifact,
    selection_records: Sequence[Mapping[str, Any]],
    adapted_records: Sequence[Mapping[str, Any]],
    registry_entry: ModelRegistryEntry,
    registry_sha256: str,
    raw_sha256: str,
    decision_sha256: str,
) -> Mapping[str, Any]:
    """Issue a private exclusion input from one retained failed response.

    This is the supported issuer for the adjudication record.  It first proves
    that the candidate's journal contains an unreconciled response, asks the
    existing Stage B parser to reconstruct it without a transport, and derives
    every response/flag/exclusion digest from that result.  It never accepts a
    hand-entered claim description or response hash.
    """

    selections = {
        _required_str(selection, "candidate_id"): selection
        for selection in selection_records
    }
    if len(selections) != 1:
        raise StageBManifestError(
            "frozen-unit adjudication issuer requires exactly one candidate"
        )
    candidate_id, selection = next(iter(selections.items()))
    units_by_candidate = _prediction_units_by_candidate(adapted_records)
    decisions_by_candidate = _verified_stage_b_decisions(artifact)
    frozen_units = tuple(units_by_candidate[candidate_id])
    decision_text, commitment = decisions_by_candidate[candidate_id]
    prompt = _labeling_prompt(
        selection,
        decision_text,
        frozen_units,
        decision_text_commitment=commitment,
    )
    journal_path = _provider_attempt_journal_path(output_root, provider)
    caps_sha256 = _authority_identity(
        raw_sha256=raw_sha256,
        decision_sha256=decision_sha256,
        registry_sha256=registry_sha256,
        provider=provider,
    )
    journal = _provider_attempt_journal(
        path=journal_path,
        stage="llm-label",
        candidate_id=candidate_id,
        prompt=prompt,
        registry_entry=registry_entry,
        account=f"cycle1-{provider}",
        model_registry_sha256=registry_sha256,
        cycle_cap_usd=PROVIDER_CAP_USD[provider],
        cycle_id="cycle-1-stage-b-manifest",
        provider_cycle_caps_sha256=caps_sha256,
    )
    if journal is None:
        raise StageBManifestError("frozen-unit issuer requires an attempt journal")
    workflow_error: FrozenUnitWorkflowRequiredError | None = None
    with journal:
        if (
            not journal.has_reconstruction_failure
            and not journal.has_validated_response
        ) or journal.has_settled_attempt:
            raise StageBManifestError(
                "frozen-unit issuer requires one unsettled retained response"
            )
    try:
        _llm_label_one_model(
            selection=selection,
            decision_text=decision_text,
            decision_text_commitment=commitment,
            frozen_units=frozen_units,
            prompt=prompt,
            registry_entry=registry_entry,
            model_registry_sha256=registry_sha256,
            transport=None,
            environ=None,
            timeout_seconds=120.0,
            max_provider_attempts=1,
            provider_journal_path=journal_path,
            provider_cycle_cap_usd=PROVIDER_CAP_USD[provider],
            provider_cycle_id="cycle-1-stage-b-manifest",
            provider_cycle_caps_sha256=caps_sha256,
            provider_spend_authorities=None,
            provider_accounts={provider: f"cycle1-{provider}"},
            replay_only=True,
        )
    except FrozenUnitWorkflowRequiredError as exc:
        workflow_error = exc
    else:
        raise StageBManifestError(
            "frozen-unit issuer did not observe the expected missing-unit flag"
        )
    evidence_journal = _provider_attempt_journal(
        path=journal_path,
        stage="llm-label",
        candidate_id=candidate_id,
        prompt=prompt,
        registry_entry=registry_entry,
        account=f"cycle1-{provider}",
        model_registry_sha256=registry_sha256,
        cycle_cap_usd=PROVIDER_CAP_USD[provider],
        cycle_id="cycle-1-stage-b-manifest",
        provider_cycle_caps_sha256=caps_sha256,
    )
    if evidence_journal is None:
        raise StageBManifestError("frozen-unit issuer could not reopen the journal")
    with evidence_journal:
        if evidence_journal.has_validated_response:
            evidence_journal.record_reconstruction_failure(workflow_error)
        evidence = evidence_journal.latest_reconstruction_recovery_evidence()
    missing_flags = [
        flag.to_record(workflow_error.labeling_result.decision_text)
        for flag in workflow_error.labeling_result.missing_unit_flags
    ]
    exclusion_entry = workflow_error.repair_result.exclusion_entry
    if exclusion_entry is None:
        raise StageBManifestError("missing-unit issuer lacks an exclusion ledger entry")
    frozen_unit_ids = [unit.unit_id for unit in frozen_units]
    owner_ruling = _owner_ruling_payload(
        candidate_id=candidate_id,
        case_id=_required_str(selection, "case_id"),
        frozen_unit_ids=frozen_unit_ids,
        missing_flags=missing_flags,
    )
    record: JsonRecord = {
        "schema_version": str(_ADJ_SCHEMA),
        "candidate_id": candidate_id,
        "case_id": _required_str(selection, "case_id"),
        "provider": provider,
        "status": "missing_unit_excluded_from_scoring",
        "owner_comment_id": owner_comment_id,
        "owner_ruling": owner_ruling,
        "owner_ruling_sha256": _owner_comment_ruling_sha256(
            owner_comment_id,
            expected_ruling=owner_ruling,
        ),
        "source_commitments": {
            "raw_prediction_units_sha256": raw_sha256,
            "selection_sha256": CURRENT_SELECTION_SHA256,
            "decision_texts_sha256": decision_sha256,
            "model_registry_sha256": registry_sha256,
            "decision_text_sha256": commitment["decision_text_sha256"],
            "raw_candidate_envelope_sha256": artifact.finalized_unit_envelope_sha256s[
                candidate_id
            ],
        },
        "frozen_unit_ids": frozen_unit_ids,
        "score_scope": "frozen_units_only",
        "scoreable_unit_ids": frozen_unit_ids,
        "raw_output_sha256": workflow_error.response.raw_output_sha256,
        "normalized_response_sha256": str(
            ARTIFACT_PREFIXED_SHA256_V1.commit(
                evidence.normalized_response_json,
                domain=_ADJ_SCHEMA,
            ).digest
        ),
        "missing_unit_flags_sha256": canonical_records_sha256(missing_flags),
        "exclusion_entry_sha256": canonical_sha256(exclusion_entry.to_record()),
    }
    _validate_frozen_unit_adjudication(
        record,
        selection=selection,
        frozen_units=frozen_units,
        decision_commitment=commitment,
        artifact=artifact,
        raw_sha256=raw_sha256,
        decision_sha256=decision_sha256,
        registry_sha256=registry_sha256,
    )
    index_payload = (
        json.dumps(
            {
                "schema_version": FROZEN_UNIT_ADJUDICATION_INDEX_V1,
                "records": [record],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode()
    _write_create_only(output_path, index_payload)
    return {
        "candidate_id": candidate_id,
        "output": str(output_path),
        "output_sha256": _raw_sha256(index_payload),
        "provider_transport_calls": 0,
        "missing_unit_flag_count": len(missing_flags),
        "frozen_unit_count": len(frozen_units),
    }


def _json_object(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        value: object = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise StageBManifestError(f"{label} is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise StageBManifestError(f"{label} is not a JSON object")
    return cast(Mapping[str, object], value)


def _validated_supporting_evidence_sidecar(
    *,
    result_path: Path,
    result_bytes: bytes,
    candidate_id: str,
    provider: str,
    model_key: str,
    frozen_unit_ids: set[str],
) -> Mapping[str, Any] | None:
    """Authenticate an advisory sidecar without making it authoritative."""

    sidecar_path = _supporting_evidence_sidecar_path(result_path)
    if not sidecar_path.exists() and not sidecar_path.is_symlink():
        return None
    sidecar = _json_object(
        _read_regular(sidecar_path, f"supporting evidence sidecar {sidecar_path}"),
        f"supporting evidence sidecar {sidecar_path}",
    )
    expected_identity = {
        "kind": SUPPORTING_EVIDENCE_SIDECAR_KIND,
        "authoritative": False,
        "result_sha256": _raw_sha256(result_bytes),
        "candidate_id": candidate_id,
        "provider": provider,
        "model_key": model_key,
        "supporting_evidence_status": "unresolved_advisory",
    }
    for key, expected in expected_identity.items():
        if sidecar.get(key) != expected:
            raise StageBManifestError(
                f"supporting evidence sidecar identity differs: {sidecar_path}/{key}"
            )
    affected_value = sidecar.get("supporting_evidence_affected_unit_ids")
    if not isinstance(affected_value, list) or not affected_value:
        raise StageBManifestError(
            f"supporting evidence sidecar affected unit IDs are invalid: {sidecar_path}"
        )
    affected_ids = cast(list[object], affected_value)
    if any(
        not isinstance(unit_id, str) or not unit_id.strip() for unit_id in affected_ids
    ):
        raise StageBManifestError(
            f"supporting evidence sidecar affected unit IDs are invalid: {sidecar_path}"
        )
    affected_strings = tuple(cast(str, unit_id) for unit_id in affected_ids)
    if len(set(affected_strings)) != len(affected_strings):
        raise StageBManifestError(
            "supporting evidence sidecar affected unit IDs are duplicated: "
            f"{sidecar_path}"
        )
    if not set(affected_strings) <= frozen_unit_ids:
        raise StageBManifestError(
            f"supporting evidence sidecar affected unit IDs differ: {sidecar_path}"
        )
    return dict(sidecar)


def _canonical_jsonl(records: Iterable[Mapping[str, object]]) -> bytes:
    return b"".join(
        json.dumps(
            dict(record), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        + b"\n"
        for record in records
    )


def _write_create_only(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        existing = _read_regular(path, f"create-only output {path}")
        if existing != payload:
            raise StageBManifestError(f"create-only output differs: {path}")
        return
    with path.open("xb") as stream:
        stream.write(payload)


def _owner_approval_ids() -> tuple[str, ...]:
    """Return exact owner comment IDs for spend and the terminal packet."""

    def comments(bead_id: str) -> list[Mapping[str, object]]:
        try:
            completed = subprocess.run(
                ["bd", "comments", bead_id, "--json"],
                check=True,
                capture_output=True,
                text=True,
            )
            value: object = json.loads(completed.stdout)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise StageBManifestError(
                f"could not read owner approval from Beads: {bead_id}"
            ) from exc
        if not isinstance(value, list):
            raise StageBManifestError(
                f"Beads comments response is not an array: {bead_id}"
            )
        return [
            cast(Mapping[str, object], raw)
            for raw in cast(list[object], value)
            if isinstance(raw, Mapping)
        ]

    spend_comments = comments(BEAD_ID)
    terminal_comments = comments(TERMINAL_APPROVAL_BEAD_ID)
    spend_ids: list[str] = []
    terminal_ids: list[str] = []
    owner_author = _owner_author()
    for comment in spend_comments:
        if comment.get("author") != owner_author:
            continue
        text = comment.get("text")
        comment_id = comment.get("id")
        if not isinstance(text, str) or not isinstance(comment_id, str):
            continue
        if text == SPEND_APPROVAL:
            spend_ids.append(comment_id)
    for comment in terminal_comments:
        if comment.get("author") != owner_author:
            continue
        text = comment.get("text")
        comment_id = comment.get("id")
        if text == TERMINAL_PACKET_APPROVAL and isinstance(comment_id, str):
            terminal_ids.append(comment_id)
    if not spend_ids:
        raise StageBManifestError("exact USD 300 Stage B owner approval is missing")
    if not terminal_ids:
        raise StageBManifestError("terminal-unit packet approval is missing")
    return tuple(sorted(set((*spend_ids, *terminal_ids))))


# contract-ratchet: allow exact owner-comment commitment bound to adjudication schema
def _owner_comment_ruling_sha256(
    comment_id: str,
    *,
    expected_ruling: Mapping[str, Any],
) -> str:
    """Return the digest of an exact, typed owner adjudication comment."""

    expected_text = "stage-b-exclusion: " + json.dumps(
        dict(expected_ruling), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )

    owner_author = _owner_author()
    for bead_id in (BEAD_ID, TERMINAL_APPROVAL_BEAD_ID):
        try:
            completed = subprocess.run(
                ["bd", "comments", bead_id, "--json"],
                check=True,
                capture_output=True,
                text=True,
            )
            value: object = json.loads(completed.stdout)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise StageBManifestError(
                f"could not read owner adjudication from Beads: {bead_id}"
            ) from exc
        if not isinstance(value, list):
            raise StageBManifestError(
                f"Beads comments response is not an array: {bead_id}"
            )
        for raw_comment in cast(list[object], value):
            if not isinstance(raw_comment, Mapping):
                continue
            comment = cast(Mapping[str, object], raw_comment)
            if comment.get("id") != comment_id or comment.get("author") != owner_author:
                continue
            text = comment.get("text")
            if not isinstance(text, str) or not text.strip():
                raise StageBManifestError("owner adjudication comment text is invalid")
            if text != expected_text:
                candidate_id = expected_ruling.get("candidate_id")
                case_id = expected_ruling.get("case_id")
                frozen_unit_ids = expected_ruling.get("frozen_unit_ids")
                missing_descriptions = expected_ruling.get("missing_unit_descriptions")
                missing_description_values = (
                    cast(list[object], missing_descriptions)
                    if isinstance(missing_descriptions, list)
                    else []
                )
                contextual_scope = (
                    comment_id == CONTEXTUAL_OWNER_APPROVAL_COMMENT_ID
                    and str(
                        ARTIFACT_PREFIXED_SHA256_V1.commit(
                            text,
                            domain=_ADJ_SCHEMA,
                        ).digest
                    )
                    == CONTEXTUAL_OWNER_APPROVAL_TEXT_SHA256
                    and expected_ruling.get("action") == "exclude_missing_unit_only"
                    and isinstance(candidate_id, str)
                    and str(
                        ARTIFACT_PREFIXED_SHA256_V1.commit(
                            candidate_id,
                            domain=_ADJ_SCHEMA,
                        ).digest
                    )
                    == CONTEXTUAL_OWNER_APPROVAL_CANDIDATE_SHA256
                    and isinstance(case_id, str)
                    and str(
                        ARTIFACT_PREFIXED_SHA256_V1.commit(
                            case_id,
                            domain=_ADJ_SCHEMA,
                        ).digest
                    )
                    == CONTEXTUAL_OWNER_APPROVAL_CANDIDATE_SHA256
                    and isinstance(frozen_unit_ids, list)
                    and len(cast(list[object], frozen_unit_ids)) == 4
                    and all(
                        isinstance(unit_id, str)
                        for unit_id in cast(list[object], frozen_unit_ids)
                    )
                    and len(missing_description_values) == 1
                    and isinstance(missing_description_values[0], str)
                    and str(
                        ARTIFACT_PREFIXED_SHA256_V1.commit(
                            missing_description_values[0],
                            domain=_ADJ_SCHEMA,
                        ).digest
                    )
                    == CONTEXTUAL_OWNER_APPROVAL_MISSING_UNIT_SHA256
                )
                if contextual_scope:
                    return str(
                        ARTIFACT_PREFIXED_SHA256_V1.commit(
                            text,
                            domain=_ADJ_SCHEMA,
                        ).digest
                    )
                raise StageBManifestError(
                    "owner adjudication comment is not the exact typed ruling"
                )
            return str(
                ARTIFACT_PREFIXED_SHA256_V1.commit(
                    text,
                    domain=_ADJ_SCHEMA,
                ).digest
            )
    raise StageBManifestError(
        f"owner adjudication comment is missing or not authored by {owner_author}: "
        f"{comment_id}"
    )


def _load_frozen_unit_adjudications(
    path: Path | None,
) -> tuple[dict[str, JsonRecord], str | None]:
    """Load the private, owner-comment-bound exclusion decisions, if supplied."""

    if path is None:
        return {}, None
    payload = _read_regular(path, "frozen-unit adjudications")
    value = _json_object(payload, "frozen-unit adjudications")
    if value.get("schema_version") != FROZEN_UNIT_ADJUDICATION_INDEX_V1:
        raise StageBManifestError("frozen-unit adjudication index schema differs")
    records_value = value.get("records")
    if not isinstance(records_value, Sequence) or isinstance(
        records_value, (str, bytes)
    ):
        raise StageBManifestError("frozen-unit adjudication records are missing")
    records: dict[str, JsonRecord] = {}
    for raw_record in cast(Sequence[object], records_value):
        if not isinstance(raw_record, Mapping):
            raise StageBManifestError("frozen-unit adjudication is not an object")
        record = dict(cast(Mapping[str, Any], raw_record))
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in records:
            raise StageBManifestError(
                f"duplicate frozen-unit adjudication: {candidate_id}"
            )
        records[candidate_id] = record
    return records, _raw_sha256(payload)


def _owner_ruling_payload(
    *,
    candidate_id: str,
    case_id: str,
    frozen_unit_ids: Sequence[str],
    missing_flags: Sequence[Mapping[str, Any]],
) -> JsonRecord:
    """Describe the only owner action permitted for this missing-unit path."""

    return {
        "action": "exclude_missing_unit_only",
        "candidate_id": candidate_id,
        "case_id": case_id,
        "frozen_unit_ids": list(frozen_unit_ids),
        "missing_unit_descriptions": [
            _required_str(flag, "missing_unit_description") for flag in missing_flags
        ],
    }


def _validate_frozen_unit_adjudication(
    record: Mapping[str, Any],
    *,
    selection: Mapping[str, Any],
    frozen_units: Sequence[Any],
    decision_commitment: Mapping[str, str],
    artifact: VerifiedDecisionTextArtifact,
    raw_sha256: str,
    decision_sha256: str,
    registry_sha256: str,
    verify_owner: bool = True,
) -> None:
    """Check source commitments before a provider-free exclusion replay."""

    if record.get("schema_version") != str(_ADJ_SCHEMA):
        raise StageBManifestError("frozen-unit adjudication schema differs")
    candidate_id = _required_str(selection, "candidate_id")
    if record.get("candidate_id") != candidate_id or record.get(
        "case_id"
    ) != _required_str(selection, "case_id"):
        raise StageBManifestError("frozen-unit adjudication candidate identity differs")
    owner_comment_id = record.get("owner_comment_id")
    owner_ruling_sha256 = record.get("owner_ruling_sha256")
    owner_ruling_value = record.get("owner_ruling")
    if (
        not isinstance(owner_comment_id, str)
        or not isinstance(owner_ruling_sha256, str)
        or not isinstance(owner_ruling_value, Mapping)
    ):
        raise StageBManifestError("frozen-unit adjudication owner identity is missing")
    owner_ruling = cast(Mapping[str, Any], owner_ruling_value)
    expected_unit_ids = [_unit_id(unit) for unit in frozen_units]
    if (
        owner_ruling.get("action") != "exclude_missing_unit_only"
        or owner_ruling.get("candidate_id") != candidate_id
        or owner_ruling.get("case_id") != _required_str(selection, "case_id")
        or owner_ruling.get("frozen_unit_ids") != expected_unit_ids
    ):
        raise StageBManifestError("frozen-unit adjudication owner ruling differs")
    if (
        verify_owner
        and _owner_comment_ruling_sha256(
            owner_comment_id,
            expected_ruling=owner_ruling,
        )
        != owner_ruling_sha256
    ):
        raise StageBManifestError("frozen-unit adjudication owner comment differs")
    source_commitments = record.get("source_commitments")
    if not isinstance(source_commitments, Mapping):
        raise StageBManifestError("frozen-unit adjudication source commitments missing")
    expected_source_commitments = {
        "raw_prediction_units_sha256": raw_sha256,
        "selection_sha256": CURRENT_SELECTION_SHA256,
        "decision_texts_sha256": decision_sha256,
        "model_registry_sha256": registry_sha256,
        "decision_text_sha256": decision_commitment.get("decision_text_sha256"),
        "raw_candidate_envelope_sha256": artifact.finalized_unit_envelope_sha256s[
            candidate_id
        ],
    }
    if dict(cast(Mapping[str, Any], source_commitments)) != expected_source_commitments:
        raise StageBManifestError("frozen-unit adjudication source commitments differ")
    if record.get("frozen_unit_ids") != expected_unit_ids:
        raise StageBManifestError("frozen-unit adjudication changed frozen units")
    if record.get("status") != "missing_unit_excluded_from_scoring":
        raise StageBManifestError("frozen-unit adjudication status differs")
    if record.get("score_scope") != "frozen_units_only":
        raise StageBManifestError("frozen-unit adjudication score scope differs")
    if record.get("scoreable_unit_ids") != expected_unit_ids:
        raise StageBManifestError("frozen-unit adjudication scoreable units differ")


def _additional_attempt_approval_id() -> str:
    """Require the exact owner approval for one same-model repair."""

    try:
        completed = subprocess.run(
            ["bd", "comments", BEAD_ID, "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        value: object = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise StageBManifestError(
            "could not read the additional-attempt owner approval from Beads"
        ) from exc
    if not isinstance(value, list):
        raise StageBManifestError("Beads comments response is not an array")
    matches: list[Mapping[str, object]] = []
    for raw in cast(list[object], value):
        if not isinstance(raw, Mapping):
            continue
        comment = cast(Mapping[str, object], raw)
        if (
            comment.get("id") == ADDITIONAL_ATTEMPT_APPROVAL_COMMENT_ID
            and comment.get("author") == _owner_author()
            and comment.get("text") == ADDITIONAL_ATTEMPT_APPROVAL_TEXT
        ):
            matches.append(comment)
    if len(matches) != 1:
        raise StageBManifestError("exact Stage B repair owner approval is missing")
    return ADDITIONAL_ATTEMPT_APPROVAL_COMMENT_ID


def _additional_attempt_permit(
    *,
    candidate_id: str,
    provider: str,
    account: str,
    registry_entry: ModelRegistryEntry,
    prompt: str,
    journal_path: Path,
    cycle_id: str,
) -> AdditionalAttemptPermit:
    """Bind the approved repair to the exact Stage B call and journal."""

    scope = provider_prompt_logical_call_scope(prompt)
    logical_key = ProviderSpendKey(
        cycle_id=cycle_id,
        provider=provider,
        account=account,
        stage="llm-label",
        model_key=registry_entry.registry_key,
        case_id=candidate_id,
        ablation="labeling",
        repeat_index=1,
    ).logical_call_key
    return AdditionalAttemptPermit(
        logical_call_key=logical_key,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        journal_path_sha256=hashlib.sha256(
            str(journal_path.resolve()).encode("utf-8")
        ).hexdigest(),
        max_total_attempts=ADDITIONAL_ATTEMPT_MAX_TOTAL,
        reservation_cap_microusd=conservative_reservation_microusd(
            context_limit=registry_entry.context_limit,
            max_output_tokens=registry_entry.max_output_tokens,
            input_token_price=registry_entry.input_token_price,
            output_token_price=registry_entry.output_token_price,
            long_context_surcharge=registry_entry.long_context_surcharge,
        ),
        provider_logical_call_scope_sha256=hashlib.sha256(scope.encode()).hexdigest(),
    )


def _manifest_units(raw_records: Sequence[Mapping[str, Any]]) -> tuple[JsonRecord, ...]:
    """Derive a local validation view without claiming Stage-A finalization."""

    envelopes: list[JsonRecord] = []
    for raw in raw_records:
        candidate_id = _required_str(raw, "candidate_id")
        case_id = _required_str(raw, "case_id")
        units_value = raw.get("prediction_units")
        if not isinstance(units_value, Sequence) or isinstance(
            units_value, (str, bytes)
        ):
            raise StageBManifestError(
                f"raw units missing prediction_units: {candidate_id}"
            )
        units: list[JsonRecord] = []
        for unit_value in cast(Sequence[object], units_value):
            if not isinstance(unit_value, Mapping):
                raise StageBManifestError(f"raw unit is not an object: {candidate_id}")
            unit = dict(cast(Mapping[str, Any], unit_value))
            unit_id = _required_str(unit, "unit_id")
            digest = canonical_sha256(unit)
            unit.update(
                {
                    "source_unit_sha256s": [digest],
                    "adjudication_id": f"automatic:{digest}",
                    "adjudication_sha256": None,
                    "disposition": "ACCEPT",
                }
            )
            if unit.get("unit_id") != unit_id:
                raise StageBManifestError(
                    "unit identity changed while adapting raw units"
                )
            units.append(unit)
        if not units:
            raise StageBManifestError(f"raw units envelope is empty: {candidate_id}")
        envelopes.append(
            {
                "schema_version": str(LEGACY_FINALIZED_SCHEMA_VERSION),
                "status": "finalized",
                "candidate_id": candidate_id,
                "case_id": case_id,
                "raw_prediction_units_sha256": canonical_sha256(raw),
                "unitization_review_queue_sha256": canonical_records_sha256(()),
                "prediction_units": units,
                "exclusion": None,
            }
        )
    return tuple(envelopes)


def _validate_raw_inputs(raw_path: Path) -> tuple[JsonRecord, ...]:
    raw_bytes = _read_regular(raw_path, "raw prediction units")
    if _raw_sha256(raw_bytes) != RAW_UNITS_SHA256:
        raise StageBManifestError(
            "raw prediction-units bytes differ from owner commitment"
        )
    records = _jsonl(raw_bytes, "raw prediction units")
    if len(records) != EXPECTED_CASE_COUNT:
        raise StageBManifestError(
            f"expected {EXPECTED_CASE_COUNT} raw cases, got {len(records)}"
        )
    candidate_ids = [_required_str(record, "candidate_id") for record in records]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise StageBManifestError(
            "raw prediction units contain duplicate candidate IDs"
        )
    unit_count = sum(
        len(cast(Sequence[object], record["prediction_units"])) for record in records
    )
    if unit_count != EXPECTED_UNIT_COUNT:
        raise StageBManifestError(
            f"expected {EXPECTED_UNIT_COUNT} raw units, got {unit_count}"
        )
    return records


def _validate_registry(registry_path: Path) -> tuple[ModelRegistryEntry, ...]:
    registry_bytes = _read_regular(registry_path, "Stage B model registry")
    if _raw_sha256(registry_bytes) != STAGE_B_REGISTRY_SHA256:
        raise StageBManifestError("Stage B registry bytes differ from owner commitment")
    registry = load_model_registry(registry_path)
    by_key = {entry.registry_key: entry for entry in registry.entries}
    if set(by_key) != set(MODEL_KEYS):
        raise StageBManifestError(
            "registry must contain exactly the two approved Stage B model keys"
        )
    for entry in by_key.values():
        if (
            not entry.network_disabled
            or not entry.search_disabled
            or entry.tool_policy.value != "no_tools"
        ):
            raise StageBManifestError(
                f"unsafe Stage B registry policy: {entry.registry_key}"
            )
    return tuple(by_key[key] for key in MODEL_KEYS)


def _current_decision_record(
    *,
    selection: Mapping[str, Any],
    decision_store_root: Path,
    input_commitments: Mapping[str, str],
) -> JsonRecord:
    candidate_id = _required_str(selection, "candidate_id")
    case_id = _required_str(selection, "case_id")
    outcome_documents: list[Mapping[str, Any]] = []
    for value in cast(Sequence[object], selection.get("documents")):
        if not isinstance(value, Mapping):
            continue
        document_value = cast(Mapping[str, Any], value)
        if (
            document_value.get("contains_target_outcome") is True
            and document_value.get("model_visible") is False
            and document_value.get("document_role") in {"decision", "order"}
        ):
            outcome_documents.append(document_value)
    if len(outcome_documents) != 1:
        raise StageBManifestError(
            f"expected exactly one outcome document: {candidate_id}"
        )
    document = outcome_documents[0]
    source_document_id = _required_str(document, "source_document_id")
    expected_source = REPLACEMENT_SOURCE_COMMITMENTS.get(source_document_id)
    if expected_source is None:
        raise StageBManifestError(
            f"replacement decision source is not owner-pinned: {candidate_id}"
        )
    metadata_path = decision_store_root / f"{source_document_id}.metadata.json"
    markdown_path = decision_store_root / f"{source_document_id}.md"
    metadata_bytes = _read_regular(metadata_path, "decision metadata")
    if _raw_sha256(metadata_bytes) != expected_source["metadata_sha256"]:
        raise StageBManifestError(
            f"replacement decision metadata bytes differ: {candidate_id}"
        )
    metadata = _json_object(metadata_bytes, "decision metadata")
    markdown = _read_regular(markdown_path, "decision markdown")
    if _raw_sha256(markdown) != expected_source["markdown_sha256"]:
        raise StageBManifestError(
            f"replacement decision markdown bytes differ: {candidate_id}"
        )
    if (
        metadata.get("candidate_id") != candidate_id
        or metadata.get("source_document_id") != source_document_id
        or metadata.get("status") != "succeeded"
    ):
        raise StageBManifestError(
            f"decision metadata identity differs: {candidate_id}/{source_document_id}"
        )
    extracted = metadata.get("extracted_text")
    if not isinstance(extracted, Mapping):
        raise StageBManifestError(
            f"decision metadata lacks extracted_text: {candidate_id}"
        )
    extracted_record = cast(Mapping[str, object], extracted)
    markdown_sha256 = _raw_sha256(markdown)
    if extracted_record.get("text_sha256") != markdown_sha256:
        raise StageBManifestError(f"decision markdown hash differs: {candidate_id}")
    source_path_value = metadata.get("input_path")
    source_sha256 = metadata.get("source_sha256")
    if not isinstance(source_path_value, str) or not isinstance(source_sha256, str):
        raise StageBManifestError(
            f"decision metadata lacks source binding: {candidate_id}"
        )
    source_path = Path(source_path_value)
    source_bytes = _read_regular(source_path, "decision source PDF")
    if _raw_sha256(source_bytes) != source_sha256:
        raise StageBManifestError(f"decision source PDF hash differs: {candidate_id}")
    if source_sha256 != expected_source["source_sha256"]:
        raise StageBManifestError(
            f"replacement decision PDF commitment differs: {candidate_id}"
        )
    try:
        text = markdown.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StageBManifestError(
            f"decision markdown is not UTF-8: {candidate_id}"
        ) from exc
    docket_entry = document.get("docket_entry_number")
    if not isinstance(docket_entry, int):
        raise StageBManifestError(f"decision docket entry is missing: {candidate_id}")
    entered_date = selection.get("decision_date")
    if not isinstance(entered_date, str) or not entered_date:
        raise StageBManifestError(f"decision date is missing: {candidate_id}")
    return {
        "schema_version": DECISION_TEXT_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "case_id": case_id,
        "document_id": f"{candidate_id}-entry-{docket_entry}-decision",
        "source_document_id": source_document_id,
        "document_role": document.get("document_role"),
        "docket_entry_number": docket_entry,
        "entered_date": entered_date,
        "is_first_written_disposition": True,
        "contains_target_outcome": True,
        "model_visible": False,
        "extraction_method": extracted_record.get("extraction_method"),
        "parser_revision": cast(
            Mapping[str, object], metadata.get("parser_config", {})
        ).get("parser_revision"),
        "source_byte_count": len(source_bytes),
        "source_sha256": source_sha256,
        "markdown_sha256": markdown_sha256,
        "text_sha256": markdown_sha256,
        "text": text,
        "input_commitments": dict(input_commitments),
    }


def _verified_inputs(
    *,
    raw_path: Path,
    decision_texts_path: Path,
    selection_path: Path,
    decision_store_root: Path,
    adapted_path: Path,
    raw_records: Sequence[Mapping[str, Any]],
) -> tuple[
    VerifiedDecisionTextArtifact, tuple[JsonRecord, ...], tuple[JsonRecord, ...]
]:
    decision_bytes = _read_regular(decision_texts_path, "decision texts")
    if _raw_sha256(decision_bytes) != DECISION_TEXTS_SHA256:
        raise StageBManifestError("decision-text bytes differ from owner commitment")
    legacy_decisions = _jsonl(decision_bytes, "decision texts")
    if len(legacy_decisions) != EXPECTED_CASE_COUNT:
        raise StageBManifestError("decision-text count is not exactly 100")
    selection_bytes = _read_regular(selection_path, "selection")
    if _raw_sha256(selection_bytes) != CURRENT_SELECTION_SHA256:
        raise StageBManifestError(
            "selection bytes differ from current Stage51 commitment"
        )
    selection_records = _jsonl(selection_bytes, "selection")
    adapted_records = _manifest_units(raw_records)
    adapted_bytes = _canonical_jsonl(adapted_records)
    _write_create_only(adapted_path, adapted_bytes)
    selected_by_id = {
        _required_str(record, "candidate_id"): record for record in selection_records
    }
    if len(selected_by_id) != EXPECTED_CASE_COUNT or set(selected_by_id) != {
        _required_str(record, "candidate_id") for record in raw_records
    }:
        raise StageBManifestError("selection and raw-unit candidate coverage differ")
    legacy_by_id = {
        _required_str(record, "candidate_id"): record for record in legacy_decisions
    }
    shared_commitments = {
        "legacy_decision_texts_sha256": DECISION_TEXTS_SHA256,
        "raw_prediction_units_sha256": RAW_UNITS_SHA256,
        "selection_sha256": CURRENT_SELECTION_SHA256,
    }
    decisions: list[JsonRecord] = []
    replacement_source_ids: set[str] = set()
    for candidate_id, selection in selected_by_id.items():
        legacy = legacy_by_id.get(candidate_id)
        if legacy is None:
            documents = selection.get("documents")
            if not isinstance(documents, Sequence) or isinstance(
                documents, (str, bytes)
            ):
                raise StageBManifestError(
                    f"selection documents are missing: {candidate_id}"
                )
            for raw_document in cast(Sequence[object], documents):
                if not isinstance(raw_document, Mapping):
                    continue
                document = cast(Mapping[str, Any], raw_document)
                if (
                    document.get("contains_target_outcome") is True
                    and document.get("model_visible") is False
                    and document.get("document_role") in {"decision", "order"}
                ):
                    source_document_id = document.get("source_document_id")
                    if isinstance(source_document_id, str):
                        replacement_source_ids.add(source_document_id)
            record = _current_decision_record(
                selection=selection,
                decision_store_root=decision_store_root,
                input_commitments=shared_commitments,
            )
        else:
            record = dict(legacy)
            if record.get("case_id") != selection.get("case_id") or record.get(
                "entered_date"
            ) != selection.get("decision_date"):
                raise StageBManifestError(
                    "retained decision text differs from current selection: "
                    f"{candidate_id}"
                )
            record["input_commitments"] = dict(shared_commitments)
        normalized_text = _required_str(record, "text")
        record["text"] = normalized_text
        record["text_sha256"] = _raw_sha256(normalized_text.encode("utf-8"))
        decisions.append(record)
    if replacement_source_ids != set(REPLACEMENT_SOURCE_COMMITMENTS):
        raise StageBManifestError(
            "replacement decision source coverage differs from owner commitments"
        )
    decision_payload = _canonical_jsonl(decisions)
    current_decision_path = adapted_path.parent / "decision-texts-current.jsonl"
    _write_create_only(current_decision_path, decision_payload)
    manifest = {
        "schema_version": str(STAGE_B_MANIFEST_DECISION_TEXTS_V1),
        **shared_commitments,
        "replacement_source_commitments": {
            source_id: dict(commitment)
            for source_id, commitment in sorted(REPLACEMENT_SOURCE_COMMITMENTS.items())
        },
        "record_count": len(decisions),
        "decision_texts_sha256": _raw_sha256(decision_payload),
        "record_sha256s": {
            _required_str(record, "candidate_id"): canonical_sha256(record)
            for record in decisions
        },
    }
    manifest_payload = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    manifest_path = adapted_path.parent / "decision-texts-current-manifest.json"
    _write_create_only(manifest_path, manifest_payload)
    run_card = {
        "schema_version": str(STAGE_B_MANIFEST_DECISION_TEXTS_RUN_V1),
        "status": "completed",
        "paid_activity_executed": False,
        "manifest_sha256": _raw_sha256(manifest_payload),
        "decision_texts_sha256": _raw_sha256(decision_payload),
    }
    run_card_payload = (
        json.dumps(run_card, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    run_card_path = adapted_path.parent / "decision-texts-current-run-card.json"
    _write_create_only(run_card_path, run_card_payload)
    artifact = VerifiedDecisionTextArtifact(
        records=tuple(decisions),
        decision_texts_sha256=_raw_sha256(decision_payload),
        manifest_sha256=_raw_sha256(manifest_payload),
        run_card_sha256=_raw_sha256(run_card_payload),
        finalized_prediction_units_sha256=RAW_UNITS_SHA256,
        finalized_unit_envelope_sha256s={
            _required_str(record, "candidate_id"): canonical_sha256(raw)
            for record, raw in zip(adapted_records, raw_records, strict=True)
        },
        input_commitments=shared_commitments,
    )
    _verified_stage_b_decisions(artifact)
    return artifact, selection_records, adapted_records


def _source_digest(path: Path) -> str:
    return _raw_sha256(_read_regular(path, str(path)))


def _result_path(output_root: Path, provider: str, candidate_id: str) -> Path:
    safe_candidate = "".join(
        character
        for character in candidate_id
        if character.isalnum() or character in "-_"
    )
    if safe_candidate != candidate_id or not safe_candidate:
        raise StageBManifestError(
            f"unsafe candidate ID for output path: {candidate_id}"
        )
    return output_root / "results" / provider / f"{safe_candidate}.json"


def _additional_attempt_result_path(
    output_root: Path, provider: str, candidate_id: str
) -> Path:
    """Keep the failed first receipt while publishing the bounded retry result."""

    canonical = _result_path(output_root, provider, candidate_id)
    return canonical.with_name(f"{canonical.stem}.attempt-2{canonical.suffix}")


def _provider_free_recovery_result_path(
    output_root: Path, provider: str, candidate_id: str
) -> Path:
    """Keep a failed receipt while publishing a corrected replay result."""

    canonical = _result_path(output_root, provider, candidate_id)
    return canonical.with_name(f"{canonical.stem}.recovered{canonical.suffix}")


def _supporting_evidence_sidecar_path(result_path: Path) -> Path:
    """Return the non-authoritative advisory sidecar beside one result receipt."""

    return result_path.with_name(f"{result_path.stem}.supporting-evidence.json")


def _preferred_result_path(output_root: Path, provider: str, candidate_id: str) -> Path:
    """Prefer a successful replay receipt over a preserved failed receipt."""

    recovered = _provider_free_recovery_result_path(output_root, provider, candidate_id)
    retry = _additional_attempt_result_path(output_root, provider, candidate_id)
    if recovered.exists() and retry.exists():
        raise StageBManifestError(
            "provider has both provider-free recovery and additional-attempt "
            f"receipts: {provider}/{candidate_id}"
        )
    if recovered.exists():
        return recovered
    if retry.exists():
        return retry
    return _result_path(output_root, provider, candidate_id)


def _shard_artifact_paths(
    output_root: Path, provider: str, max_cases: int | None
) -> tuple[Path, Path]:
    stem = f"{provider}-provider-shard"
    suffix = "" if max_cases is None else f"-canary-{max_cases}"
    return (
        output_root / f"{stem}{suffix}-audit.jsonl",
        output_root / f"{stem}{suffix}-run-card.json",
    )


def _provider_attempt_journal_path(output_root: Path, provider: str) -> Path:
    """Return the canonical attempt journal path for one provider shard.

    The journal identity includes the provider-specific caps commitment.  A
    shared filename therefore cannot be reused by the OpenAI and Google
    shards, even when both shards share an output root.
    """

    normalized_provider = provider.strip().lower()
    if normalized_provider not in PROVIDER_CAP_USD:
        raise StageBManifestError(f"unsupported execution provider: {provider}")
    return output_root / f"provider-attempts-{normalized_provider}.sqlite3"


def _unit_id(value: Any) -> str:
    if isinstance(value, Mapping):
        return _required_str(cast(Mapping[str, Any], value), "unit_id")
    unit_id = getattr(value, "unit_id", None)
    if not isinstance(unit_id, str) or not unit_id:
        raise StageBManifestError("frozen unit lacks a valid unit_id")
    return unit_id


def _existing_result(
    path: Path,
    *,
    candidate_id: str,
    provider: str,
    model_key: str,
    raw_sha256: str,
    raw_candidate_envelope_sha256: str,
    decision_sha256: str,
    registry_sha256: str,
    selection: Mapping[str, Any],
    frozen_units: Sequence[Any],
    decision_commitment: Mapping[str, str],
    prompt: str,
    frozen_unit_adjudication: Mapping[str, Any] | None = None,
) -> JsonRecord | None:
    if not path.exists():
        return None
    value_bytes = _read_regular(path, f"existing result {path}")
    value = _json_object(value_bytes, f"existing result {path}")
    if SUPPORTING_EVIDENCE_SIDECAR_FIELDS.intersection(value):
        raise StageBManifestError(
            f"existing result carries non-authoritative advisory fields: {path}"
        )
    expected = {
        "schema_version": str(STAGE_B_MANIFEST_PROVIDER_RESULT_V1),
        "candidate_id": candidate_id,
        "case_id": _required_str(selection, "case_id"),
        "provider": provider,
        "model_key": model_key,
        "raw_prediction_units_sha256": raw_sha256,
        "raw_candidate_envelope_sha256": raw_candidate_envelope_sha256,
        "decision_texts_sha256": decision_sha256,
        "model_registry_sha256": registry_sha256,
        "provider_sampling_policy": "provider_default",
        "tools_enabled": False,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise StageBManifestError(f"existing result identity differs: {path}")
    status = value.get("status")
    if status == "failed":
        if frozen_unit_adjudication is None:
            raise StageBManifestError(
                f"existing failed result requires frozen-unit adjudication: {path}"
            )
        archived_path = path.with_name(path.name + ".failed")
        if archived_path.exists():
            raise StageBManifestError(
                f"failed result archive already exists; refusing to overwrite: "
                f"{archived_path}"
            )
        path.rename(archived_path)
        return None
    if status != "succeeded":
        raise StageBManifestError(f"existing result status differs: {path}")
    audit_value = value.get("audit")
    if not isinstance(audit_value, Mapping):
        raise StageBManifestError(f"existing result audit is missing: {path}")
    audit = cast(Mapping[str, Any], audit_value)
    if SUPPORTING_EVIDENCE_SIDECAR_FIELDS.intersection(audit):
        raise StageBManifestError(
            f"existing result audit carries non-authoritative advisory fields: {path}"
        )
    expected_audit = {
        "stage": "llm-label-provider-shard",
        "status": "succeeded",
        "candidate_id": candidate_id,
        "case_id": _required_str(selection, "case_id"),
        "execution_provider": provider,
        "model_keys": [model_key],
        "frozen_panel_model_keys": list(MODEL_KEYS),
        "model_registry_sha256": registry_sha256,
        "decision_text_commitment": dict(decision_commitment),
        "label_count": 0,
        "unit_count": len(frozen_units),
    }
    for key, expected_value in expected_audit.items():
        if audit.get(key) != expected_value:
            raise StageBManifestError(f"existing result audit identity differs: {path}")
    if frozen_unit_adjudication is not None:
        existing_adjudication = audit.get("frozen_unit_adjudication")
        if existing_adjudication != dict(frozen_unit_adjudication):
            raise StageBManifestError(
                f"existing result frozen-unit adjudication differs: {path}"
            )
        workflow = audit.get("frozen_unit_workflow")
        if (
            not isinstance(workflow, Mapping)
            or cast(Mapping[str, Any], workflow).get("is_scored") is not False
            or cast(Mapping[str, Any], workflow).get("score_scope")
            != "frozen_units_only"
            or cast(Mapping[str, Any], workflow).get("scoreable_unit_ids")
            != [_unit_id(unit) for unit in frozen_units]
        ):
            raise StageBManifestError(
                f"existing result frozen-unit workflow differs: {path}"
            )
        missing_flags = audit.get("missing_unit_flags")
        if not isinstance(missing_flags, Sequence) or isinstance(
            missing_flags, (str, bytes)
        ):
            raise StageBManifestError(
                f"existing result missing-unit evidence is missing: {path}"
            )
        if frozen_unit_adjudication.get("missing_unit_flags_sha256") != (
            canonical_records_sha256(cast(Sequence[Mapping[str, Any]], missing_flags))
        ):
            raise StageBManifestError(
                f"existing result missing-unit evidence differs: {path}"
            )
        exclusion_value = cast(Mapping[str, Any], workflow).get("exclusion")
        if not isinstance(exclusion_value, Mapping):
            raise StageBManifestError(
                f"existing result exclusion evidence differs: {path}"
            )
        exclusion = cast(Mapping[str, Any], exclusion_value)
        if frozen_unit_adjudication.get("exclusion_entry_sha256") != canonical_sha256(
            exclusion
        ):
            raise StageBManifestError(
                f"existing result exclusion evidence differs: {path}"
            )
    model_outputs = audit.get("model_outputs")
    if not isinstance(model_outputs, Sequence) or isinstance(
        model_outputs, (str, bytes)
    ):
        raise StageBManifestError(f"existing result model outputs are missing: {path}")
    model_output_values = cast(Sequence[object], model_outputs)
    if len(model_output_values) != 1 or not isinstance(model_output_values[0], Mapping):
        raise StageBManifestError(
            f"existing result model output coverage differs: {path}"
        )
    model_output = cast(Mapping[str, Any], model_output_values[0])
    if SUPPORTING_EVIDENCE_SIDECAR_FIELDS.intersection(model_output):
        raise StageBManifestError(
            "existing result model output carries non-authoritative advisory "
            f"fields: {path}"
        )
    expected_prompt_sha256 = "sha256:" + _raw_sha256(prompt.encode("utf-8"))
    if model_output.get("model_key") != model_key:
        raise StageBManifestError(f"existing result model identity differs: {path}")
    if frozen_unit_adjudication is not None and model_output.get(
        "raw_output_sha256"
    ) != frozen_unit_adjudication.get("raw_output_sha256"):
        raise StageBManifestError(
            f"existing result response commitment differs: {path}"
        )
    if model_output.get("provider_prompt_sha256") != expected_prompt_sha256:
        raise StageBManifestError(f"existing result prompt commitment differs: {path}")
    metadata_value = model_output.get("metadata")
    if not isinstance(metadata_value, Mapping):
        raise StageBManifestError(
            f"existing result provider metadata is missing: {path}"
        )
    metadata = cast(Mapping[str, Any], metadata_value)
    model_id = model_key.split(":", 1)[1]
    expected_metadata = {
        "provider": provider,
        "model": model_id,
        "model_id": model_id,
        "model_registry_sha256": registry_sha256,
        "provider_sampling_policy": "provider_default",
        "tool_policy": "no_tools",
    }
    for key, expected_value in expected_metadata.items():
        if metadata.get(key) != expected_value:
            raise StageBManifestError(
                f"existing result nested provider metadata differs: {path}"
            )
    labels = model_output.get("labels")
    if not isinstance(labels, Sequence) or isinstance(labels, (str, bytes)):
        raise StageBManifestError(f"existing result labels are missing: {path}")
    expected_unit_ids = {_unit_id(unit) for unit in frozen_units}
    label_values = cast(Sequence[object], labels)
    if len(expected_unit_ids) != len(frozen_units) or len(label_values) != len(
        frozen_units
    ):
        raise StageBManifestError(f"existing result label coverage differs: {path}")
    actual_unit_ids: set[str] = set()
    for raw_label in label_values:
        if not isinstance(raw_label, Mapping):
            raise StageBManifestError(f"existing result label is not an object: {path}")
        try:
            label = _outcome_label(cast(Mapping[str, Any], raw_label))
        except (TypeError, ValueError) as exc:
            raise StageBManifestError(
                f"existing result label is invalid: {path}"
            ) from exc
        if label.unit_id in actual_unit_ids:
            raise StageBManifestError(f"existing result has duplicate labels: {path}")
        actual_unit_ids.add(label.unit_id)
    if actual_unit_ids != expected_unit_ids:
        raise StageBManifestError(f"existing result unit coverage differs: {path}")
    return dict(cast(Mapping[str, Any], value))


def _existing_failure_result(
    path: Path,
    *,
    candidate_id: str,
    provider: str,
    model_key: str,
    raw_sha256: str,
    raw_candidate_envelope_sha256: str,
    decision_sha256: str,
    registry_sha256: str,
    selection: Mapping[str, Any],
    allow_any_validation_failure: bool = False,
    expected_error_message: str | None = None,
) -> JsonRecord:
    """Authenticate a preserved failed receipt before a new result receipt."""

    value = _json_object(
        _read_regular(path, f"existing failed result {path}"),
        f"existing failed result {path}",
    )
    expected = {
        "schema_version": str(STAGE_B_MANIFEST_PROVIDER_RESULT_V1),
        "status": "failed",
        "candidate_id": candidate_id,
        "case_id": _required_str(selection, "case_id"),
        "provider": provider,
        "model_key": model_key,
        "model_registry_sha256": registry_sha256,
        "raw_prediction_units_sha256": raw_sha256,
        "raw_candidate_envelope_sha256": raw_candidate_envelope_sha256,
        "decision_texts_sha256": decision_sha256,
        "provider_sampling_policy": "provider_default",
        "tools_enabled": False,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise StageBManifestError(
                f"existing failed result identity differs: {path}/{key}"
            )
    valid_failure = (
        value.get("error_type") == ADDITIONAL_ATTEMPT_FAILURE_TYPE
        and value.get("error_message") == ADDITIONAL_ATTEMPT_FAILURE_MESSAGE
    )
    if allow_any_validation_failure:
        valid_failure = (
            value.get("error_type") == "LlmResponseValidationError"
            and isinstance(value.get("error_message"), str)
            and bool(str(value["error_message"]).strip())
        )
    if not valid_failure:
        raise StageBManifestError(
            f"existing failed result is not the approved citation-validation "
            f"failure: {path}"
        )
    if (
        expected_error_message is not None
        and value.get("error_message") != expected_error_message
    ):
        raise StageBManifestError(
            f"existing failed result differs from journal evidence: {path}"
        )
    return dict(value)


def _reconstruction_failure_evidence(
    *,
    journal_path: Path,
    candidate_id: str,
    prompt: str,
    registry_entry: ModelRegistryEntry,
    registry_sha256: str,
    provider: str,
    raw_sha256: str,
    decision_sha256: str,
) -> ReconstructionFailureEvidence | None:
    """Read the exact retained response and validation error, if present."""

    journal = _provider_attempt_journal(
        path=journal_path,
        stage="llm-label",
        candidate_id=candidate_id,
        prompt=prompt,
        registry_entry=registry_entry,
        account=f"cycle1-{provider}",
        model_registry_sha256=registry_sha256,
        cycle_cap_usd=PROVIDER_CAP_USD[provider],
        cycle_id="cycle-1-stage-b-manifest",
        provider_cycle_caps_sha256=_authority_identity(
            raw_sha256=raw_sha256,
            decision_sha256=decision_sha256,
            registry_sha256=registry_sha256,
            provider=provider,
        ),
    )
    if journal is None:
        return None
    with journal:
        if not journal.has_reconstruction_failure:
            return None
        try:
            return journal.latest_reconstruction_recovery_evidence()
        except ProviderJournalError as exc:
            raise StageBManifestError(
                "additional attempt lacks immutable journal evidence"
            ) from exc


def _additional_attempt_prompt(
    *, original_prompt: str, evidence: ReconstructionFailureEvidence
) -> str:
    try:
        normalized: object = json.loads(evidence.normalized_response_json)
    except json.JSONDecodeError as exc:
        raise StageBManifestError("journaled provider response is invalid") from exc
    raw_output = (
        cast(Mapping[str, object], normalized).get("raw_output")
        if isinstance(normalized, Mapping)
        else None
    )
    if not isinstance(raw_output, str):
        raise StageBManifestError("journaled provider response lacks raw_output")
    return json.dumps(
        {
            "instruction": "Return only corrected Stage B schema JSON.",
            "original_authenticated_prompt": original_prompt,
            "original_raw_submission": raw_output,
            "validation_error": {
                "type": evidence.failure_type,
                "message": evidence.failure_message,
            },
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )


def _authority_identity(
    *, raw_sha256: str, decision_sha256: str, registry_sha256: str, provider: str
) -> str:
    payload = json.dumps(
        {
            "bead": BEAD_ID,
            "decision_texts_sha256": decision_sha256,
            "owner_cap_usd": OWNER_CAP_USD,
            "provider": provider,
            "raw_prediction_units_sha256": raw_sha256,
            "registry_sha256": registry_sha256,
            "spend_approval": SPEND_APPROVAL,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return _raw_sha256(payload)


def _execute_provider(
    *,
    provider: str,
    output_root: Path,
    raw_path: Path,
    decision_texts_path: Path,
    artifact: VerifiedDecisionTextArtifact,
    selection_records: Sequence[Mapping[str, Any]],
    adapted_records: Sequence[Mapping[str, Any]],
    registry_entry: ModelRegistryEntry,
    registry_sha256: str,
    raw_sha256: str,
    decision_sha256: str,
    max_cases: int | None,
    frozen_unit_adjudications: Mapping[str, Mapping[str, Any]] | None = None,
    frozen_unit_adjudications_sha256: str | None = None,
    additional_attempt_candidate: str | None = None,
    owner_comment_ids: Sequence[str] | None = None,
) -> tuple[JsonRecord, ...]:
    del raw_path, decision_texts_path
    if provider not in PROVIDER_CAP_USD:
        raise StageBManifestError(f"unsupported execution provider: {provider}")
    units_by_candidate = _prediction_units_by_candidate(adapted_records)
    decisions_by_candidate = _verified_stage_b_decisions(artifact)
    selections_by_candidate = {
        _required_str(selection, "candidate_id"): selection
        for selection in selection_records
    }
    if set(selections_by_candidate) != set(units_by_candidate) or set(
        selections_by_candidate
    ) != set(decisions_by_candidate):
        raise StageBManifestError(
            "selection, adapted units, and decision texts do not cover the same "
            "candidates"
        )
    candidate_ids = list(selections_by_candidate)
    if max_cases is not None:
        if max_cases <= 0:
            raise StageBManifestError("max_cases must be positive")
        candidate_ids = candidate_ids[:max_cases]
    adjudications = {
        candidate_id: record
        for candidate_id, record in (frozen_unit_adjudications or {}).items()
        if record.get("provider") in {None, provider}
    }
    if not set(adjudications) <= set(selections_by_candidate):
        raise StageBManifestError(
            "frozen-unit adjudication contains an unselected candidate"
        )
    if (
        additional_attempt_candidate is not None
        and additional_attempt_candidate not in candidate_ids
    ):
        raise StageBManifestError(
            "additional-attempt candidate is outside the selected execution"
        )
    journal_path = _provider_attempt_journal_path(output_root, provider)
    authority_path = output_root / f"spend-authority-{provider}.sqlite3"
    account = f"cycle1-{provider}"
    effective_owner_comment_ids = (
        tuple(owner_comment_ids)
        if owner_comment_ids is not None
        else (_owner_approval_ids() if additional_attempt_candidate is not None else ())
    )
    if (
        additional_attempt_candidate is not None
        and ADDITIONAL_ATTEMPT_APPROVAL_COMMENT_ID not in effective_owner_comment_ids
    ):
        raise StageBManifestError("additional attempt lacks exact owner approval")
    with SqliteProviderSpendAuthority(
        authority_path,
        authority_identity_sha256=_authority_identity(
            raw_sha256=raw_sha256,
            decision_sha256=decision_sha256,
            registry_sha256=registry_sha256,
            provider=provider,
        ),
        cycle_id="cycle-1-stage-b-manifest",
        provider=provider,
        account=account,
        cap_microusd=int(PROVIDER_CAP_USD[provider] * 1_000_000),
        policy=FrozenAttemptPolicy(
            reservation_ledger_sha256=_authority_identity(
                raw_sha256=raw_sha256,
                decision_sha256=decision_sha256,
                registry_sha256=registry_sha256,
                provider=provider,
            ),
            max_billable_attempts=1,
            failure_threshold=5,
            failure_window_seconds=86_400,
        ),
    ) as authority:
        records: list[JsonRecord] = []
        for candidate_id in candidate_ids:
            selection = selections_by_candidate[candidate_id]
            frozen_units = tuple(units_by_candidate[candidate_id])
            decision_text, commitment = decisions_by_candidate[candidate_id]
            adjudication = adjudications.get(candidate_id)
            if adjudication is not None:
                _validate_frozen_unit_adjudication(
                    adjudication,
                    selection=selection,
                    frozen_units=frozen_units,
                    decision_commitment=commitment,
                    artifact=artifact,
                    raw_sha256=raw_sha256,
                    decision_sha256=decision_sha256,
                    registry_sha256=registry_sha256,
                )
            prompt = _labeling_prompt(
                selection,
                decision_text,
                frozen_units,
                decision_text_commitment=commitment,
            )
            canonical_result_path = _result_path(output_root, provider, candidate_id)
            recovered_result_path = _provider_free_recovery_result_path(
                output_root, provider, candidate_id
            )
            retry_enabled = additional_attempt_candidate == candidate_id
            retry_result_path = _additional_attempt_result_path(
                output_root, provider, candidate_id
            )
            call_prompt = prompt
            call_scope: str | None = None
            expected_error_message: str | None = None
            if retry_enabled:
                if not canonical_result_path.exists():
                    raise StageBManifestError(
                        "additional attempt requires canonical failed receipt"
                    )
                evidence = _reconstruction_failure_evidence(
                    journal_path=journal_path,
                    candidate_id=candidate_id,
                    prompt=prompt,
                    registry_entry=registry_entry,
                    registry_sha256=registry_sha256,
                    provider=provider,
                    raw_sha256=raw_sha256,
                    decision_sha256=decision_sha256,
                )
                if evidence is None:
                    raise StageBManifestError(
                        "additional attempt requires retained validation failure"
                    )
                call_prompt = _additional_attempt_prompt(
                    original_prompt=prompt, evidence=evidence
                )
                call_scope = provider_prompt_logical_call_scope(call_prompt)
                expected_error_message = evidence.failure_message
            prior: JsonRecord | None = None
            result_path = canonical_result_path
            recovery_enabled = False
            if recovered_result_path.exists():
                _existing_failure_result(
                    canonical_result_path,
                    candidate_id=candidate_id,
                    provider=provider,
                    model_key=registry_entry.registry_key,
                    raw_sha256=raw_sha256,
                    raw_candidate_envelope_sha256=artifact.finalized_unit_envelope_sha256s[
                        candidate_id
                    ],
                    decision_sha256=decision_sha256,
                    registry_sha256=registry_sha256,
                    selection=selection,
                    allow_any_validation_failure=True,
                )
                prior = _existing_result(
                    recovered_result_path,
                    candidate_id=candidate_id,
                    provider=provider,
                    model_key=registry_entry.registry_key,
                    raw_sha256=raw_sha256,
                    raw_candidate_envelope_sha256=artifact.finalized_unit_envelope_sha256s[
                        candidate_id
                    ],
                    decision_sha256=decision_sha256,
                    registry_sha256=registry_sha256,
                    selection=selection,
                    frozen_units=frozen_units,
                    decision_commitment=commitment,
                    prompt=prompt,
                    frozen_unit_adjudication=adjudication,
                )
                result_path = recovered_result_path
            elif retry_enabled and retry_result_path.exists():
                _existing_failure_result(
                    canonical_result_path,
                    candidate_id=candidate_id,
                    provider=provider,
                    model_key=registry_entry.registry_key,
                    raw_sha256=raw_sha256,
                    raw_candidate_envelope_sha256=artifact.finalized_unit_envelope_sha256s[
                        candidate_id
                    ],
                    decision_sha256=decision_sha256,
                    registry_sha256=registry_sha256,
                    selection=selection,
                    allow_any_validation_failure=True,
                    expected_error_message=expected_error_message,
                )
                prior = _existing_result(
                    retry_result_path,
                    candidate_id=candidate_id,
                    provider=provider,
                    model_key=registry_entry.registry_key,
                    raw_sha256=raw_sha256,
                    raw_candidate_envelope_sha256=artifact.finalized_unit_envelope_sha256s[
                        candidate_id
                    ],
                    decision_sha256=decision_sha256,
                    registry_sha256=registry_sha256,
                    selection=selection,
                    frozen_units=frozen_units,
                    decision_commitment=commitment,
                    prompt=call_prompt,
                    frozen_unit_adjudication=adjudication,
                )
                result_path = retry_result_path
            elif canonical_result_path.exists():
                try:
                    prior = _existing_result(
                        canonical_result_path,
                        candidate_id=candidate_id,
                        provider=provider,
                        model_key=registry_entry.registry_key,
                        raw_sha256=raw_sha256,
                        raw_candidate_envelope_sha256=artifact.finalized_unit_envelope_sha256s[
                            candidate_id
                        ],
                        decision_sha256=decision_sha256,
                        registry_sha256=registry_sha256,
                        selection=selection,
                        frozen_units=frozen_units,
                        decision_commitment=commitment,
                        prompt=prompt,
                        frozen_unit_adjudication=adjudication,
                    )
                except StageBManifestError as existing_error:
                    if retry_enabled:
                        _existing_failure_result(
                            canonical_result_path,
                            candidate_id=candidate_id,
                            provider=provider,
                            model_key=registry_entry.registry_key,
                            raw_sha256=raw_sha256,
                            raw_candidate_envelope_sha256=artifact.finalized_unit_envelope_sha256s[
                                candidate_id
                            ],
                            decision_sha256=decision_sha256,
                            registry_sha256=registry_sha256,
                            selection=selection,
                            allow_any_validation_failure=True,
                            expected_error_message=expected_error_message,
                        )
                        result_path = retry_result_path
                    elif adjudication is None:
                        try:
                            _existing_failure_result(
                                canonical_result_path,
                                candidate_id=candidate_id,
                                provider=provider,
                                model_key=registry_entry.registry_key,
                                raw_sha256=raw_sha256,
                                raw_candidate_envelope_sha256=artifact.finalized_unit_envelope_sha256s[
                                    candidate_id
                                ],
                                decision_sha256=decision_sha256,
                                registry_sha256=registry_sha256,
                                selection=selection,
                                allow_any_validation_failure=True,
                            )
                        except StageBManifestError:
                            raise existing_error from None
                        if (
                            _reconstruction_failure_evidence(
                                journal_path=journal_path,
                                candidate_id=candidate_id,
                                prompt=prompt,
                                registry_entry=registry_entry,
                                registry_sha256=registry_sha256,
                                provider=provider,
                                raw_sha256=raw_sha256,
                                decision_sha256=decision_sha256,
                            )
                            is None
                        ):
                            raise existing_error
                        recovery_enabled = True
                        result_path = recovered_result_path
                    else:
                        raise
            if prior is not None:
                records.append(cast(JsonRecord, prior["audit"]))
                continue
            replay_only = adjudication is not None or recovery_enabled
            if not replay_only:
                _validate_provider_environment(provider)
            additional_attempt_permit = (
                _additional_attempt_permit(
                    candidate_id=candidate_id,
                    provider=provider,
                    account=account,
                    registry_entry=registry_entry,
                    prompt=call_prompt,
                    journal_path=journal_path,
                    cycle_id="cycle-1-stage-b-manifest",
                )
                if retry_enabled
                else None
            )
            authorities: Mapping[str, ProviderSpendAuthority] = {provider: authority}
            accounts = {provider: account}
            frozen_workflow_audit: JsonRecord = {}
            supporting_evidence_audit: JsonRecord = {}
            try:
                labels, response, finding_count, missing_count, prompt_sha256 = (
                    _llm_label_one_model(
                        selection=selection,
                        decision_text=decision_text,
                        decision_text_commitment=commitment,
                        frozen_units=frozen_units,
                        prompt=call_prompt,
                        registry_entry=registry_entry,
                        model_registry_sha256=registry_sha256,
                        transport=None,
                        environ=None,
                        timeout_seconds=120.0,
                        max_provider_attempts=1,
                        additional_attempt_permit=additional_attempt_permit,
                        provider_journal_path=journal_path,
                        provider_cycle_cap_usd=PROVIDER_CAP_USD[provider],
                        provider_cycle_id="cycle-1-stage-b-manifest",
                        provider_cycle_caps_sha256=_authority_identity(
                            raw_sha256=raw_sha256,
                            decision_sha256=decision_sha256,
                            registry_sha256=registry_sha256,
                            provider=provider,
                        ),
                        provider_spend_authorities=authorities,
                        provider_accounts=accounts,
                        frozen_unit_adjudication=adjudication,
                        frozen_unit_workflow_audit=frozen_workflow_audit,
                        replay_only=replay_only,
                        supporting_evidence_audit=(
                            supporting_evidence_audit if recovery_enabled else None
                        ),
                        provider_logical_call_scope=call_scope,
                    )
                )
            except Exception as exc:
                failure = {
                    "schema_version": (str(STAGE_B_MANIFEST_PROVIDER_RESULT_V1)),
                    "status": "failed",
                    "candidate_id": candidate_id,
                    "case_id": _required_str(selection, "case_id"),
                    "provider": provider,
                    "model_key": registry_entry.registry_key,
                    "model_registry_sha256": registry_sha256,
                    "raw_prediction_units_sha256": raw_sha256,
                    "raw_candidate_envelope_sha256": (
                        artifact.finalized_unit_envelope_sha256s[candidate_id]
                    ),
                    "decision_texts_sha256": decision_sha256,
                    "provider_sampling_policy": "provider_default",
                    "tools_enabled": False,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
                if isinstance(exc, FrozenUnitWorkflowRequiredError):
                    failure.update(_frozen_unit_workflow_audit_fields(exc))
                if not recovery_enabled:
                    _write_create_only(
                        result_path,
                        (
                            json.dumps(
                                failure,
                                ensure_ascii=False,
                                sort_keys=True,
                                indent=2,
                            )
                            + "\n"
                        ).encode(),
                    )
                raise
            model_output = {
                "model_key": registry_entry.registry_key,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "estimated_cost": response.estimated_cost,
                "raw_output_sha256": response.raw_output_sha256,
                "finding_count": finding_count,
                "missing_unit_flag_count": missing_count,
                "provider_prompt_sha256": prompt_sha256,
                "metadata": dict(response.metadata or {}),
                "labels": [label.to_record() for label in labels],
            }
            if adjudication is not None:
                if frozen_workflow_audit.get("frozen_unit_adjudication") != dict(
                    adjudication
                ):
                    raise StageBManifestError(
                        "frozen-unit adjudication replay produced no matching audit"
                    )
                model_output.update(frozen_workflow_audit)
            audit: JsonRecord = {
                "stage": "llm-label-provider-shard",
                "status": "succeeded",
                "candidate_id": candidate_id,
                "case_id": _required_str(selection, "case_id"),
                "execution_provider": provider,
                "model_keys": [registry_entry.registry_key],
                "frozen_panel_model_keys": list(MODEL_KEYS),
                "model_registry_sha256": registry_sha256,
                "decision_text_commitment": commitment,
                "label_count": 0,
                "unit_count": len(frozen_units),
                "model_outputs": [model_output],
                "estimated_cost": response.estimated_cost,
            }
            if frozen_workflow_audit:
                audit.update(frozen_workflow_audit)
            result = {
                "schema_version": str(STAGE_B_MANIFEST_PROVIDER_RESULT_V1),
                "status": "succeeded",
                "candidate_id": candidate_id,
                "case_id": _required_str(selection, "case_id"),
                "provider": provider,
                "model_key": registry_entry.registry_key,
                "model_registry_sha256": registry_sha256,
                "raw_prediction_units_sha256": raw_sha256,
                "raw_candidate_envelope_sha256": (
                    artifact.finalized_unit_envelope_sha256s[candidate_id]
                ),
                "decision_texts_sha256": decision_sha256,
                "provider_sampling_policy": "provider_default",
                "tools_enabled": False,
                "audit": audit,
            }
            result_payload = (
                json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            ).encode()
            _write_create_only(
                result_path,
                result_payload,
            )
            if supporting_evidence_audit:
                sidecar = {
                    "kind": SUPPORTING_EVIDENCE_SIDECAR_KIND,
                    "authoritative": False,
                    "result_sha256": _raw_sha256(result_payload),
                    "candidate_id": candidate_id,
                    "provider": provider,
                    "model_key": registry_entry.registry_key,
                    **supporting_evidence_audit,
                }
                sidecar_payload = (
                    json.dumps(sidecar, ensure_ascii=False, sort_keys=True, indent=2)
                    + "\n"
                ).encode()
                _write_create_only(
                    _supporting_evidence_sidecar_path(result_path), sidecar_payload
                )
            records.append(audit)
        audit_payload = _canonical_jsonl(records)
        audit_path, run_card_path = _shard_artifact_paths(
            output_root, provider, max_cases
        )
        _write_create_only(audit_path, audit_payload)
        run_card = {
            "schema_version": str(STAGE_B_MANIFEST_PROVIDER_SHARD_RUN_CARD_V1),
            "stage": "llm-label-provider-shard",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": True,
            "paid_activity_executed": True,
            "execution_provider": provider,
            "model_keys": list(MODEL_KEYS),
            "executed_model_keys": [registry_entry.registry_key],
            "source_commitments": {
                "raw_prediction_units": raw_sha256,
                "selection": CURRENT_SELECTION_SHA256,
                "legacy_decision_texts": DECISION_TEXTS_SHA256,
                "decision_texts_current": decision_sha256,
                "model_registry": registry_sha256,
                "terminal_packet_approval": TERMINAL_PACKET_APPROVAL,
            },
            "output_commitments": {
                "audit": _raw_sha256(audit_payload),
                "result_root": str(output_root / "results" / provider),
                "provider_attempt_journal": _source_digest(journal_path),
            },
            "owner_comment_ids": list(effective_owner_comment_ids),
            "provider_sampling_policy": "provider_default",
            "tools_enabled": False,
            "create_only": True,
            "resumable": True,
            "max_cases": max_cases,
            "case_count": len(records),
            "unit_count": sum(int(record.get("unit_count", 0)) for record in records),
        }
        if frozen_unit_adjudications_sha256 is not None and adjudications:
            run_card["source_commitments"] = {
                **cast(Mapping[str, Any], run_card["source_commitments"]),
                "frozen_unit_adjudications": frozen_unit_adjudications_sha256,
            }
        run_card_payload = (
            json.dumps(run_card, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode()
        _write_create_only(run_card_path, run_card_payload)
    return tuple(records)


def _validate_full_provider_shard(
    *,
    output_root: Path,
    provider: str,
    registry_entry: ModelRegistryEntry,
    registry_sha256: str,
    raw_sha256: str,
    decision_sha256: str,
    artifact: VerifiedDecisionTextArtifact,
    selection_records: Sequence[Mapping[str, Any]],
    adapted_records: Sequence[Mapping[str, Any]],
    owner_comment_ids: Sequence[str],
    frozen_unit_adjudications: Mapping[str, Mapping[str, Any]] | None = None,
    frozen_unit_adjudications_sha256: str | None = None,
) -> tuple[tuple[JsonRecord, ...], Mapping[str, Any]]:
    """Authenticate one complete provider shard without touching credentials."""

    normalized_provider = provider.lower()
    provider_adjudications = {
        candidate_id: record
        for candidate_id, record in (frozen_unit_adjudications or {}).items()
        if record.get("provider") in {None, normalized_provider}
    }
    expected_owner_comment_ids = tuple(owner_comment_ids)
    candidate_ids = {
        _required_str(selection, "candidate_id") for selection in selection_records
    }
    if any(
        _additional_attempt_result_path(
            output_root, normalized_provider, candidate_id
        ).exists()
        for candidate_id in candidate_ids
    ):
        approval_id = _additional_attempt_approval_id()
        if approval_id not in expected_owner_comment_ids:
            expected_owner_comment_ids = (
                *expected_owner_comment_ids,
                approval_id,
            )
    audit_path, run_card_path = _shard_artifact_paths(
        output_root, normalized_provider, None
    )
    audit_bytes = _read_regular(audit_path, "provider shard audit")
    audit_rows = _jsonl(audit_bytes, "provider shard audit")
    if len(audit_rows) != EXPECTED_CASE_COUNT:
        raise StageBManifestError(
            f"{normalized_provider} provider shard is not complete: "
            f"expected {EXPECTED_CASE_COUNT} rows, got {len(audit_rows)}"
        )
    run_card_bytes = _read_regular(run_card_path, "provider shard run card")
    run_card = _json_object(run_card_bytes, "provider shard run card")
    expected_source_commitments = {
        "raw_prediction_units": raw_sha256,
        "selection": CURRENT_SELECTION_SHA256,
        "legacy_decision_texts": DECISION_TEXTS_SHA256,
        "decision_texts_current": decision_sha256,
        "model_registry": registry_sha256,
        "terminal_packet_approval": TERMINAL_PACKET_APPROVAL,
    }
    expected_card = {
        "schema_version": str(STAGE_B_MANIFEST_PROVIDER_SHARD_RUN_CARD_V1),
        "stage": "llm-label-provider-shard",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": True,
        "paid_activity_executed": True,
        "execution_provider": normalized_provider,
        "model_keys": list(MODEL_KEYS),
        "executed_model_keys": [registry_entry.registry_key],
        "provider_sampling_policy": "provider_default",
        "tools_enabled": False,
        "create_only": True,
        "resumable": True,
        "max_cases": None,
        "case_count": EXPECTED_CASE_COUNT,
        "unit_count": EXPECTED_UNIT_COUNT,
        "owner_comment_ids": list(expected_owner_comment_ids),
    }
    for key, expected_value in expected_card.items():
        if run_card.get(key) != expected_value:
            raise StageBManifestError(
                f"provider shard run card field differs: {normalized_provider}/{key}"
            )
    if frozen_unit_adjudications_sha256 is not None and provider_adjudications:
        expected_source_commitments = {
            **expected_source_commitments,
            "frozen_unit_adjudications": frozen_unit_adjudications_sha256,
        }
    if run_card.get("source_commitments") != expected_source_commitments:
        raise StageBManifestError(
            f"provider shard source commitments differ: {normalized_provider}"
        )
    output_commitments_value = run_card.get("output_commitments")
    if not isinstance(output_commitments_value, Mapping):
        raise StageBManifestError(
            f"provider shard output commitments are missing: {normalized_provider}"
        )
    output_commitments = cast(Mapping[str, Any], output_commitments_value)
    if output_commitments.get("audit") != _raw_sha256(audit_bytes):
        raise StageBManifestError(
            f"provider shard audit commitment differs: {normalized_provider}"
        )
    journal_path = _provider_attempt_journal_path(output_root, normalized_provider)
    try:
        journal_digest = _source_digest(journal_path)
    except (OSError, StageBManifestError) as exc:
        raise StageBManifestError(
            "provider shard attempt journal is missing or unreadable: "
            f"{normalized_provider}"
        ) from exc
    if output_commitments.get("provider_attempt_journal") != journal_digest:
        raise StageBManifestError(
            f"provider shard attempt journal commitment differs: {normalized_provider}"
        )

    units_by_candidate = _prediction_units_by_candidate(adapted_records)
    decisions_by_candidate = _verified_stage_b_decisions(artifact)
    selections_by_candidate = {
        _required_str(selection, "candidate_id"): selection
        for selection in selection_records
    }
    if set(selections_by_candidate) != set(units_by_candidate) or set(
        selections_by_candidate
    ) != set(decisions_by_candidate):
        raise StageBManifestError("merge inputs do not cover the same candidates")

    expected_audits: list[JsonRecord] = []
    supporting_evidence_sidecars: dict[str, Mapping[str, Any]] = {}
    repair_prompt_sha256s: dict[str, tuple[str, str]] = {}
    for candidate_id, selection in selections_by_candidate.items():
        frozen_units = tuple(units_by_candidate[candidate_id])
        decision_text, commitment = decisions_by_candidate[candidate_id]
        prompt = _labeling_prompt(
            selection,
            decision_text,
            frozen_units,
            decision_text_commitment=commitment,
        )
        result_path = _preferred_result_path(
            output_root, normalized_provider, candidate_id
        )
        result_prompt = prompt
        if result_path == _additional_attempt_result_path(
            output_root, normalized_provider, candidate_id
        ):
            evidence = _reconstruction_failure_evidence(
                journal_path=journal_path,
                candidate_id=candidate_id,
                prompt=prompt,
                registry_entry=registry_entry,
                registry_sha256=registry_sha256,
                provider=normalized_provider,
                raw_sha256=raw_sha256,
                decision_sha256=decision_sha256,
            )
            if evidence is None:
                raise StageBManifestError(
                    "additional-attempt result lacks original journal evidence"
                )
            result_prompt = _additional_attempt_prompt(
                original_prompt=prompt, evidence=evidence
            )
            repair_prompt_sha256s[candidate_id] = (
                "sha256:" + _raw_sha256(prompt.encode()),
                "sha256:" + _raw_sha256(result_prompt.encode()),
            )
        adjudication = provider_adjudications.get(candidate_id)
        if adjudication is not None:
            _validate_frozen_unit_adjudication(
                adjudication,
                selection=selection,
                frozen_units=frozen_units,
                decision_commitment=commitment,
                artifact=artifact,
                raw_sha256=raw_sha256,
                decision_sha256=decision_sha256,
                registry_sha256=registry_sha256,
            )
        result = _existing_result(
            result_path,
            candidate_id=candidate_id,
            provider=normalized_provider,
            model_key=registry_entry.registry_key,
            raw_sha256=raw_sha256,
            raw_candidate_envelope_sha256=artifact.finalized_unit_envelope_sha256s[
                candidate_id
            ],
            decision_sha256=decision_sha256,
            registry_sha256=registry_sha256,
            selection=selection,
            frozen_units=frozen_units,
            decision_commitment=commitment,
            prompt=result_prompt,
            frozen_unit_adjudication=(provider_adjudications.get(candidate_id)),
        )
        if result is None:
            raise StageBManifestError(
                "provider shard receipt is missing: "
                f"{normalized_provider}/{candidate_id}"
            )
        if result_path.exists() or result_path.is_symlink():
            result_bytes = _read_regular(result_path, f"provider result {result_path}")
            sidecar = _validated_supporting_evidence_sidecar(
                result_path=result_path,
                result_bytes=result_bytes,
                candidate_id=candidate_id,
                provider=normalized_provider,
                model_key=registry_entry.registry_key,
                frozen_unit_ids={_unit_id(unit) for unit in frozen_units},
            )
            if sidecar is not None:
                supporting_evidence_sidecars[candidate_id] = sidecar
        audit = result.get("audit")
        if not isinstance(audit, Mapping):
            raise StageBManifestError(
                "provider shard receipt audit is missing: "
                f"{normalized_provider}/{candidate_id}"
            )
        audit = cast(Mapping[str, Any], audit)
        if adjudication is not None:
            model_outputs_value = audit.get("model_outputs")
            if not isinstance(model_outputs_value, Sequence) or isinstance(
                model_outputs_value, (str, bytes)
            ):
                raise StageBManifestError(
                    "provider shard adjudication model output is missing: "
                    f"{normalized_provider}/{candidate_id}"
                )
            model_output_values = cast(Sequence[object], model_outputs_value)
            if len(model_output_values) != 1:
                raise StageBManifestError(
                    "provider shard adjudication model output is missing: "
                    f"{normalized_provider}/{candidate_id}"
                )
            model_output_value = model_output_values[0]
            if not isinstance(model_output_value, Mapping):
                raise StageBManifestError(
                    "provider shard adjudication model output is invalid: "
                    f"{normalized_provider}/{candidate_id}"
                )
            model_output = cast(Mapping[str, Any], model_output_value)
            if model_output.get("raw_output_sha256") != adjudication.get(
                "raw_output_sha256"
            ):
                raise StageBManifestError(
                    "provider shard adjudication response differs: "
                    f"{normalized_provider}/{candidate_id}"
                )
            workflow_value = audit.get("frozen_unit_workflow")
            missing_flags_value = audit.get("missing_unit_flags")
            if (
                not isinstance(workflow_value, Mapping)
                or not isinstance(missing_flags_value, Sequence)
                or isinstance(missing_flags_value, (str, bytes))
            ):
                raise StageBManifestError(
                    "provider shard adjudication evidence is incomplete: "
                    f"{normalized_provider}/{candidate_id}"
                )
            workflow = cast(Mapping[str, Any], workflow_value)
            missing_flags = cast(Sequence[Mapping[str, Any]], missing_flags_value)
            if workflow.get("score_scope") != "frozen_units_only" or workflow.get(
                "scoreable_unit_ids"
            ) != [_unit_id(unit) for unit in frozen_units]:
                raise StageBManifestError(
                    "provider shard adjudication score scope differs: "
                    f"{normalized_provider}/{candidate_id}"
                )
            if adjudication.get("missing_unit_flags_sha256") != (
                canonical_records_sha256(missing_flags)
            ):
                raise StageBManifestError(
                    "provider shard adjudication missing-unit evidence differs: "
                    f"{normalized_provider}/{candidate_id}"
                )
            exclusion_value = workflow.get("exclusion")
            if not isinstance(exclusion_value, Mapping):
                raise StageBManifestError(
                    "provider shard adjudication exclusion evidence differs: "
                    f"{normalized_provider}/{candidate_id}"
                )
            exclusion = cast(Mapping[str, Any], exclusion_value)
            if adjudication.get("exclusion_entry_sha256") != canonical_sha256(
                exclusion
            ):
                raise StageBManifestError(
                    "provider shard adjudication exclusion evidence differs: "
                    f"{normalized_provider}/{candidate_id}"
                )
            expected_owner_ruling = _owner_ruling_payload(
                candidate_id=candidate_id,
                case_id=_required_str(selection, "case_id"),
                frozen_unit_ids=[_unit_id(unit) for unit in frozen_units],
                missing_flags=missing_flags,
            )
            if adjudication.get("owner_ruling") != expected_owner_ruling:
                raise StageBManifestError(
                    "provider shard adjudication owner ruling differs: "
                    f"{normalized_provider}/{candidate_id}"
                )
            journal = _provider_attempt_journal(
                path=journal_path,
                stage="llm-label",
                candidate_id=candidate_id,
                prompt=prompt,
                registry_entry=registry_entry,
                account=f"cycle1-{normalized_provider}",
                model_registry_sha256=registry_sha256,
                cycle_cap_usd=PROVIDER_CAP_USD[normalized_provider],
                cycle_id="cycle-1-stage-b-manifest",
                provider_cycle_caps_sha256=_authority_identity(
                    raw_sha256=raw_sha256,
                    decision_sha256=decision_sha256,
                    registry_sha256=registry_sha256,
                    provider=normalized_provider,
                ),
            )
            if journal is None:
                raise StageBManifestError(
                    "provider shard adjudication journal is unavailable"
                )
            with journal:
                evidence = journal.latest_reconstruction_recovery_evidence()
                try:
                    normalized_value: object = json.loads(
                        evidence.normalized_response_json
                    )
                except json.JSONDecodeError as exc:
                    raise StageBManifestError(
                        "provider shard adjudication normalized response is not "
                        "valid JSON: "
                        f"{normalized_provider}/{candidate_id}"
                    ) from exc
                if not isinstance(normalized_value, Mapping):
                    raise StageBManifestError(
                        "provider shard adjudication normalized response is not "
                        "an object: "
                        f"{normalized_provider}/{candidate_id}"
                    )
                normalized_record = cast(Mapping[str, object], normalized_value)
                raw_output = normalized_record.get("raw_output")
                if not isinstance(raw_output, str) or not raw_output.strip():
                    raise StageBManifestError(
                        "provider shard adjudication normalized response lacks "
                        "raw_output: "
                        f"{normalized_provider}/{candidate_id}"
                    )
                journal_response = SolverResponse(raw_output=raw_output)
                expected_raw_output_sha256 = journal_response.raw_output_sha256
                if (
                    adjudication.get("raw_output_sha256") != expected_raw_output_sha256
                    or model_output.get("raw_output_sha256")
                    != expected_raw_output_sha256
                ):
                    raise StageBManifestError(
                        "provider shard adjudication raw output differs from "
                        "authenticated "
                        "provider journal: "
                        f"{normalized_provider}/{candidate_id}"
                    )
            expected_normalized_sha256 = str(
                ARTIFACT_PREFIXED_SHA256_V1.commit(
                    evidence.normalized_response_json,
                    domain=_ADJ_SCHEMA,
                ).digest
            )
            if adjudication.get("normalized_response_sha256") != (
                expected_normalized_sha256
            ):
                raise StageBManifestError(
                    "provider shard adjudication normalized response differs: "
                    f"{normalized_provider}/{candidate_id}"
                )
        expected_audits.append(dict(audit))

    if tuple(audit_rows) != tuple(expected_audits):
        raise StageBManifestError(
            f"provider shard audit does not match authenticated receipts: "
            f"{normalized_provider}"
        )
    merge_audits: list[JsonRecord] = []
    for audit in expected_audits:
        candidate_id = _required_str(audit, "candidate_id")
        sidecar = supporting_evidence_sidecars.get(candidate_id)
        repair_hashes = repair_prompt_sha256s.get(candidate_id)
        if sidecar is None and repair_hashes is None:
            merge_audits.append(audit)
            continue
        model_outputs_value = audit.get("model_outputs")
        if not isinstance(model_outputs_value, Sequence) or isinstance(
            model_outputs_value, (str, bytes)
        ):
            raise StageBManifestError(
                "provider shard advisory model output coverage differs: "
                f"{normalized_provider}/{candidate_id}"
            )
        model_output_values = cast(Sequence[object], model_outputs_value)
        if len(model_output_values) != 1:
            raise StageBManifestError(
                "provider shard advisory model output coverage differs: "
                f"{normalized_provider}/{candidate_id}"
            )
        model_output_value = model_output_values[0]
        if not isinstance(model_output_value, Mapping):
            raise StageBManifestError(
                "provider shard advisory model output is invalid: "
                f"{normalized_provider}/{candidate_id}"
            )
        enriched_output = dict(cast(Mapping[str, Any], model_output_value))
        if sidecar is not None:
            enriched_output.update(
                {
                    "supporting_evidence_status": sidecar["supporting_evidence_status"],
                    "supporting_evidence_affected_unit_ids": sidecar[
                        "supporting_evidence_affected_unit_ids"
                    ],
                }
            )
        if repair_hashes is not None:
            original_sha256, repair_sha256 = repair_hashes
            enriched_output.update(
                {
                    "provider_prompt_scope": "repair",
                    "original_provider_prompt_sha256": original_sha256,
                    "repair_prompt_sha256": repair_sha256,
                }
            )
        enriched_audit = dict(audit)
        enriched_audit["model_outputs"] = [enriched_output]
        merge_audits.append(enriched_audit)
    return tuple(merge_audits), {
        "provider": normalized_provider,
        "audit_sha256": _raw_sha256(audit_bytes),
        "run_card_sha256": _raw_sha256(run_card_bytes),
        "provider_attempt_journal": journal_digest,
        "case_count": len(expected_audits),
        "unit_count": sum(int(row.get("unit_count", 0)) for row in expected_audits),
    }


def _merge_provider_shards(
    *,
    output_root: Path,
    artifact: VerifiedDecisionTextArtifact,
    selection_records: Sequence[Mapping[str, Any]],
    adapted_records: Sequence[Mapping[str, Any]],
    registry_entries: Sequence[ModelRegistryEntry],
    owner_comment_ids: Sequence[str],
    registry_sha256: str,
    raw_sha256: str,
    decision_sha256: str,
    frozen_unit_adjudications: Mapping[str, Mapping[str, Any]] | None = None,
    frozen_unit_adjudications_sha256: str | None = None,
) -> Mapping[str, Any]:
    """Fan in complete authenticated shards and publish create-only outputs."""

    provider_audits: list[JsonRecord] = []
    shard_inputs: list[Mapping[str, Any]] = []
    for entry in registry_entries:
        audits, shard_input = _validate_full_provider_shard(
            output_root=output_root,
            provider=entry.provider,
            registry_entry=entry,
            registry_sha256=registry_sha256,
            raw_sha256=raw_sha256,
            decision_sha256=decision_sha256,
            artifact=artifact,
            selection_records=selection_records,
            adapted_records=adapted_records,
            owner_comment_ids=owner_comment_ids,
            frozen_unit_adjudications=frozen_unit_adjudications,
            frozen_unit_adjudications_sha256=frozen_unit_adjudications_sha256,
        )
        provider_audits.extend(audits)
        shard_inputs.append(shard_input)

    try:
        merged = merge_llm_label_provider_shards(
            selection_records=selection_records,
            prediction_unit_records=adapted_records,
            decision_text_artifact=artifact,
            registry_entries=registry_entries,
            provider_shard_audit_records=provider_audits,
            model_registry_sha256=registry_sha256,
        )
    except Exception as exc:
        raise StageBManifestError(f"provider shard merge failed: {exc}") from exc

    units_by_candidate = _prediction_units_by_candidate(adapted_records)
    labels_payload = _canonical_jsonl(merged.records)
    audit_payload = _canonical_jsonl(merged.audit_records)
    queue_records = lawyer_review_queue_records(merged.audit_records)
    queue_payload = _canonical_jsonl(queue_records)
    output_payloads = {
        "labels.jsonl": labels_payload,
        "llm-label-audit.jsonl": audit_payload,
        "lawyer-review-queue.jsonl": queue_payload,
    }
    for name, payload in output_payloads.items():
        _write_create_only(output_root / name, payload)

    unit_count = sum(
        len(units_by_candidate[candidate_id])
        for candidate_id in (
            _required_str(selection, "candidate_id") for selection in selection_records
        )
    )

    merge_run_card = {
        "schema_version": str(STAGE_B_MANIFEST_MERGE_RUN_CARD_V1),
        "stage": "llm-label-manifest-merge",
        "status": "completed",
        "execute": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "provider_credentials_required": False,
        "source_commitments": {
            "raw_prediction_units": raw_sha256,
            "selection": CURRENT_SELECTION_SHA256,
            "legacy_decision_texts": DECISION_TEXTS_SHA256,
            "decision_texts_current": decision_sha256,
            "model_registry": registry_sha256,
            "terminal_packet_approval": TERMINAL_PACKET_APPROVAL,
        },
        "owner_comment_ids": list(owner_comment_ids),
        "provider_shards": shard_inputs,
        "output_commitments": {
            name.removesuffix(".jsonl").replace("-", "_"): _raw_sha256(payload)
            for name, payload in output_payloads.items()
        },
        "create_only": True,
        "resumable": True,
        "case_count": len(selection_records),
        "unit_count": unit_count,
        "label_count": len(merged.records),
        "audit_count": len(merged.audit_records),
        "lawyer_review_queue_count": len(queue_records),
    }
    if frozen_unit_adjudications_sha256 is not None:
        merge_run_card["source_commitments"] = {
            **cast(Mapping[str, Any], merge_run_card["source_commitments"]),
            "frozen_unit_adjudications": frozen_unit_adjudications_sha256,
        }
    merge_run_card_payload = (
        json.dumps(merge_run_card, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    _write_create_only(
        output_root / "llm-label-merge-run-card.json", merge_run_card_payload
    )
    return {
        "case_count": len(selection_records),
        "unit_count": merge_run_card["unit_count"],
        "label_count": len(merged.records),
        "audit_count": len(merged.audit_records),
        "lawyer_review_queue_count": len(queue_records),
        "labels": str(output_root / "labels.jsonl"),
        "audit": str(output_root / "llm-label-audit.jsonl"),
        "lawyer_review_queue": str(output_root / "lawyer-review-queue.jsonl"),
        "run_card": str(output_root / "llm-label-merge-run-card.json"),
    }


def run(args: argparse.Namespace) -> int:
    raw_path = Path(args.raw_prediction_units).resolve()
    decision_texts_path = Path(args.decision_texts).resolve()
    selection_path = Path(args.selection).resolve()
    decision_store_root = Path(args.decision_store_root).resolve()
    registry_path = Path(args.model_registry).resolve()
    output_root = Path(args.output_root).resolve()
    owner_comment_ids = _owner_approval_ids()
    raw_records = _validate_raw_inputs(raw_path)
    registry_entries = _validate_registry(registry_path)
    registry_sha256 = _source_digest(registry_path)
    raw_sha256 = _source_digest(raw_path)
    legacy_decision_sha256 = _source_digest(decision_texts_path)
    adapted_path = output_root / "stageb-manifest-input-adapter.jsonl"
    artifact, selection_records, adapted_records = _verified_inputs(
        raw_path=raw_path,
        decision_texts_path=decision_texts_path,
        selection_path=selection_path,
        decision_store_root=decision_store_root,
        adapted_path=adapted_path,
        raw_records=raw_records,
    )
    adjudication_path_value = getattr(args, "frozen_unit_adjudications", None)
    adjudication_path = (
        Path(adjudication_path_value).resolve()
        if adjudication_path_value is not None
        else None
    )
    if getattr(args, "issue_frozen_unit_adjudication", False):
        frozen_unit_adjudications, frozen_unit_adjudications_sha256 = {}, None
    else:
        frozen_unit_adjudications, frozen_unit_adjudications_sha256 = (
            _load_frozen_unit_adjudications(adjudication_path)
        )
    if registry_sha256 != STAGE_B_REGISTRY_SHA256 or raw_sha256 != RAW_UNITS_SHA256:
        raise StageBManifestError("authenticated source commitment changed")
    if legacy_decision_sha256 != DECISION_TEXTS_SHA256:
        raise StageBManifestError("legacy decision-text commitment changed")
    decision_sha256 = artifact.decision_texts_sha256
    provider = args.provider
    if getattr(args, "issue_frozen_unit_adjudication", False):
        if provider is None:
            raise StageBManifestError(
                "--issue-frozen-unit-adjudication requires --provider"
            )
        owner_comment_id = getattr(args, "owner_comment_id", None)
        candidate_id = getattr(args, "candidate_id", None)
        if not isinstance(owner_comment_id, str) or not owner_comment_id:
            raise StageBManifestError(
                "--issue-frozen-unit-adjudication requires --owner-comment-id"
            )
        if not isinstance(candidate_id, str) or not candidate_id:
            raise StageBManifestError(
                "--issue-frozen-unit-adjudication requires --candidate-id"
            )
        if adjudication_path is None:
            raise StageBManifestError(
                "--issue-frozen-unit-adjudication requires "
                "--frozen-unit-adjudications output path"
            )
        selected = tuple(
            selection
            for selection in selection_records
            if _required_str(selection, "candidate_id") == candidate_id
        )
        adapted = tuple(
            record
            for record in adapted_records
            if _required_str(record, "candidate_id") == candidate_id
        )
        if len(selected) != 1 or len(adapted) != 1:
            raise StageBManifestError(
                "candidate is not present exactly once for adjudication: "
                f"{candidate_id}"
            )
        entry = next(
            item for item in registry_entries if item.provider.lower() == provider
        )
        summary = _issue_frozen_unit_adjudication(
            output_path=adjudication_path,
            owner_comment_id=owner_comment_id,
            provider=provider,
            output_root=output_root,
            artifact=artifact,
            selection_records=selected,
            adapted_records=adapted,
            registry_entry=entry,
            registry_sha256=registry_sha256,
            raw_sha256=raw_sha256,
            decision_sha256=decision_sha256,
        )
        print(json.dumps(summary, sort_keys=True))
        return 0
    additional_attempt_candidate = getattr(args, "additional_attempt_candidate", None)
    if additional_attempt_candidate is not None:
        owner_comment_ids = (*owner_comment_ids, _additional_attempt_approval_id())
    if args.merge:
        if (
            args.execute
            or provider is not None
            or additional_attempt_candidate is not None
        ):
            raise StageBManifestError(
                "--merge cannot be combined with --execute, --provider, or retry"
            )
        summary = _merge_provider_shards(
            output_root=output_root,
            artifact=artifact,
            selection_records=selection_records,
            adapted_records=adapted_records,
            registry_entries=registry_entries,
            owner_comment_ids=owner_comment_ids,
            registry_sha256=registry_sha256,
            raw_sha256=raw_sha256,
            decision_sha256=decision_sha256,
            frozen_unit_adjudications=frozen_unit_adjudications,
            frozen_unit_adjudications_sha256=frozen_unit_adjudications_sha256,
        )
        print(json.dumps(summary, sort_keys=True))
        return 0
    if additional_attempt_candidate is not None and not args.execute:
        raise StageBManifestError("--additional-attempt-candidate requires --execute")
    if not args.execute:
        plan = {
            "schema_version": str(STAGE_B_MANIFEST_PLAN_V1),
            "execute": False,
            "owner_bead": BEAD_ID,
            "owner_comment_ids": list(owner_comment_ids),
            "owner_cap_usd": OWNER_CAP_USD,
            "estimated_cost_usd": 15.0,
            "raw_prediction_units_sha256": raw_sha256,
            "raw_case_count": len(raw_records),
            "raw_unit_count": sum(
                len(cast(Sequence[object], record["prediction_units"]))
                for record in raw_records
            ),
            "decision_texts_sha256": decision_sha256,
            "model_registry_sha256": registry_sha256,
            "model_keys": list(MODEL_KEYS),
            "provider": provider,
            "provider_sampling_policy": "provider_default",
            "tools_enabled": False,
            "create_only": True,
            "resume": True,
            "legacy_llm_unitize_path": "untouched",
            "decision_text_verified": True,
        }
        payload = (
            json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode()
        _write_create_only(output_root / "dry-run-plan.json", payload)
        print(json.dumps(plan, sort_keys=True))
        return 0
    if provider is None:
        raise StageBManifestError("--execute requires exactly one --provider shard")
    entry = next(
        (item for item in registry_entries if item.provider.lower() == provider), None
    )
    if entry is None:
        raise StageBManifestError(
            f"provider is not in the approved registry: {provider}"
        )
    audits = _execute_provider(
        provider=provider,
        output_root=output_root,
        raw_path=raw_path,
        decision_texts_path=decision_texts_path,
        artifact=artifact,
        selection_records=selection_records,
        adapted_records=adapted_records,
        registry_entry=entry,
        registry_sha256=registry_sha256,
        raw_sha256=raw_sha256,
        decision_sha256=decision_sha256,
        max_cases=args.max_cases,
        frozen_unit_adjudications=frozen_unit_adjudications,
        frozen_unit_adjudications_sha256=frozen_unit_adjudications_sha256,
        additional_attempt_candidate=additional_attempt_candidate,
        owner_comment_ids=owner_comment_ids,
    )
    print(
        json.dumps(
            {
                "provider": provider,
                "succeeded": len(audits),
                "output_root": str(output_root),
                "provider_shard_audit": str(
                    _shard_artifact_paths(output_root, provider, args.max_cases)[0]
                ),
                "provider_shard_run_card": str(
                    _shard_artifact_paths(output_root, provider, args.max_cases)[1]
                ),
            },
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-prediction-units", required=True, type=Path)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--decision-texts", required=True, type=Path)
    parser.add_argument("--decision-store-root", required=True, type=Path)
    parser.add_argument("--model-registry", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--provider", choices=("openai", "google"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--frozen-unit-adjudications",
        type=Path,
        help=(
            "private owner-comment-bound adjudication index; with "
            "--issue-frozen-unit-adjudication this is the create-only output"
        ),
    )
    parser.add_argument(
        "--issue-frozen-unit-adjudication",
        action="store_true",
        help=(
            "issue a provider-free exclusion input from one retained failed "
            "provider response"
        ),
    )
    parser.add_argument("--owner-comment-id")
    parser.add_argument("--candidate-id")
    parser.add_argument(
        "--additional-attempt-candidate",
        help=(
            "Owner-approved one additional same-model attempt for one selected "
            "failed Stage B candidate."
        ),
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Provider-free fan-in of complete authenticated provider shards.",
    )
    parser.add_argument("--max-cases", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(argv))
    except StageBManifestError as exc:
        raise SystemExit(f"stageb-manifest: {exc}") from exc


if __name__ == "__main__":
    main()
