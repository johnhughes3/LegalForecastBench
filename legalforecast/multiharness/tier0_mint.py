"""Deterministic issuer for the Tier-0 executable spec and spend sidecars.

``tier0 run`` accepts only a spec artifact addressed by hash.  Nothing in the
supported tree could produce that artifact, so the hash an approver signs had
no reproducible provenance.  This module is the issuing half of that contract:
the same inputs always produce the same bytes, and a reviewer holding the same
pin can recompute every hash the freeze names.

Two inputs are deliberately not committed to this public repository:

* the 23 upstream criterion IDs, which the pinned characterization classifies
  as evaluator-private, and which the per-criterion judge ceilings must carry
  verbatim so the runner can match each reservation to its pinned ordinal; and
* the enforced budget argument for the native-thin arm, which the operator
  must name from the command their pinned solver actually honors.

Everything else -- the dated pricing snapshot, the ceiling arithmetic, the
model and issuer identities, the arm shapes -- is a committed constant here.
The mint therefore runs inside the operator's private boundary and emits
artifacts that never enter git, while the freeze binds this generator plus its
public inputs.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from legalforecast.multiharness.harvey_lab_authorized_scoring import (
    HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
    harvey_lab_issuer_policy_sha256,
)
from legalforecast.multiharness.harvey_lab_evaluator import EVALUATOR_COMMAND_NAME
from legalforecast.multiharness.harvey_lab_projection import HarveyLabPin
from legalforecast.multiharness.spend import (
    ExperimentCeiling,
    InvocationBudget,
    JudgeCriterionCeiling,
    PricingRate,
    PricingSnapshot,
    SolverCeiling,
    SpendPolicy,
)
from legalforecast.multiharness.tier0_evaluator_wrapper import wrapper_source_sha256
from legalforecast.multiharness.tier0_production_factory import (
    JUDGE_PROVIDER,
    JUDGE_REQUESTED_MODEL,
)
from legalforecast.multiharness.tier0_runner import Tier0ArmSpec, Tier0ExecutableSpec

TIER0_EXPERIMENT_ID = "tier0-paired-smoke-2026-08-17"

# ---------------------------------------------------------------------------
# Dated pricing snapshot
#
# Source: https://platform.claude.com/docs/en/about-claude/models/overview
# (legacy-models table), fetched 2026-08-17. Claude Sonnet 4.6 is listed at
# $3 / input MTok and $15 / output MTok, which is 3 and 15 micro-USD per token.
# Only the model the spec actually uses is priced: an unused row would be a
# pricing claim nothing verifies.
# ---------------------------------------------------------------------------
PRICING_SNAPSHOT_ID = "tier0-anthropic-2026-08-17"
PRICING_AS_OF_DATE = "2026-08-17"
PRICING_SOURCE_URL = "https://platform.claude.com/docs/en/about-claude/models/overview"
PRICING_INPUT_MICROUSD_PER_TOKEN = 3
PRICING_OUTPUT_MICROUSD_PER_TOKEN = 15

# ---------------------------------------------------------------------------
# Ceiling inputs. Every dollar figure below is derived from these token caps
# and the rates above; none is a guess. ``validate_before_credentials``
# re-derives the same arithmetic and refuses a ceiling that cannot cover one
# worst-case request.
# ---------------------------------------------------------------------------
JUDGE_MAX_INPUT_TOKENS = 24_000
JUDGE_MAX_OUTPUT_TOKENS = 16
JUDGE_MAX_ATTEMPTS = 3
SOLVER_MAX_INPUT_TOKENS = 400_000
SOLVER_MAX_OUTPUT_TOKENS = 64_000
SOLVER_MAX_COST_USD = "8.000000"
CLAUDE_BUDGET_ARGUMENT = "--max-budget-usd"
LAB_CRITERION_COUNT = 23
ARM_IDS = ("arm-opaque-01", "arm-opaque-02")

# The retained issue-196 pin, from docs/adapters/harvey-lab-pinned-evaluator-seam.md.
SOURCE_PIN = HarveyLabPin(
    repository="https://github.com/harveyai/harvey-labs",
    commit="73feb91d63d53b1a44151d99329779c4defcdb72",
    tree="944913ee8cdeaef4930a106e5e16d74aa93a29d7",
)
PINNED_TASK_SHA256 = "c117cc3faf49b879f3c475b097bd67293ca79fa5b9e3d9cd91782b0f70f687e4"
PINNED_TASK_ID = "employment-labor/identify-issues-in-counterparty-motion-brief"
REQUESTED_MODEL = JUDGE_REQUESTED_MODEL

CLAUDE_EXECUTABLE_VERSION = "2.1.233 (Claude Code)"
CLAUDE_EXECUTABLE_SHA256 = (
    "sha256:55d281096f57d411ebbdd94dbf5e9ff3accb7c05713e37348c2c11d4b83bf9d9"
)


class Tier0MintError(ValueError):
    """The Tier-0 spec and sidecars could not be minted from these inputs."""


@dataclass(frozen=True, slots=True)
class NativeThinArmInput:
    """Operator-supplied identity of the pinned native-thin solver.

    ``budget_argument`` must be a flag the pinned command genuinely enforces.
    As of the 2026-07-16 upstream characterization the pinned LAB harness
    exposes ``--model``, ``--task``, ``--run-id``, ``--max-turns``,
    ``--temperature``, ``--shell-timeout``, ``--reasoning-effort``,
    ``--skills``, and ``--sandbox-image`` -- none of which is a monetary cap.
    An operator who cannot name a real one cannot mint a paid policy, which is
    the intended outcome: a turn limit is not a dollar ceiling.
    """

    executable: str
    executable_sha256: str
    executable_version: str
    version_probe_args: tuple[str, ...]
    command: tuple[str, ...]
    budget_argument: str

    def __post_init__(self) -> None:
        if not self.budget_argument.startswith("--"):
            raise Tier0MintError(
                "native-thin budget argument must be a real command-line flag"
            )
        if self.budget_argument not in self.command:
            raise Tier0MintError(
                "native-thin command does not pass its declared budget argument"
            )
        index = self.command.index(self.budget_argument)
        if (
            index + 1 >= len(self.command)
            or self.command[index + 1] != "{max_cost_usd}"
        ):
            raise Tier0MintError(
                "native-thin budget argument must be followed by {max_cost_usd}"
            )


@dataclass(frozen=True, slots=True)
class MintedTier0Artifacts:
    """The three deterministic files plus the hashes a freeze must name."""

    spec_path: Path
    pricing_path: Path
    policy_path: Path
    spec_sha256: str
    pricing_snapshot_sha256: str
    spend_policy_sha256: str

    def to_record(self) -> dict[str, object]:
        return {
            "spec_file": self.spec_path.name,
            "pricing_file": self.pricing_path.name,
            "policy_file": self.policy_path.name,
            "spec_sha256": self.spec_sha256,
            "pricing_snapshot_sha256": self.pricing_snapshot_sha256,
            "spend_policy_sha256": self.spend_policy_sha256,
        }


def build_pricing_snapshot() -> PricingSnapshot:
    """Return the dated snapshot every paid ceiling is validated against."""

    return PricingSnapshot(
        snapshot_id=PRICING_SNAPSHOT_ID,
        as_of_date=PRICING_AS_OF_DATE,
        rates=(
            PricingRate(
                provider=JUDGE_PROVIDER,
                model=REQUESTED_MODEL,
                input_microusd_per_token=PRICING_INPUT_MICROUSD_PER_TOKEN,
                output_microusd_per_token=PRICING_OUTPUT_MICROUSD_PER_TOKEN,
            ),
        ),
    )


def judge_max_cost_usd(pricing: PricingSnapshot) -> str:
    """Return the smallest whole-cent cap covering one worst-case judge call."""

    rate = pricing.rate_for(JUDGE_PROVIDER, REQUESTED_MODEL)
    worst_case = rate.worst_case_microusd(
        input_tokens=JUDGE_MAX_INPUT_TOKENS, output_tokens=JUDGE_MAX_OUTPUT_TOKENS
    )
    cents = -(-worst_case // 10_000)
    return format(Decimal(cents * 10_000) / Decimal(1_000_000), "f")


def experiment_max_cost_usd(pricing: PricingSnapshot) -> str:
    """Return the experiment-wide stop that covers every authorized request."""

    judge_cap = Decimal(judge_max_cost_usd(pricing))
    judge_total = judge_cap * LAB_CRITERION_COUNT * JUDGE_MAX_ATTEMPTS * len(ARM_IDS)
    solver_total = Decimal(SOLVER_MAX_COST_USD) * len(ARM_IDS)
    return format(judge_total + solver_total, "f")


def experiment_max_requests() -> int:
    """Return the request stop: one solver call and every judge attempt."""

    return len(ARM_IDS) * (1 + LAB_CRITERION_COUNT * JUDGE_MAX_ATTEMPTS)


def build_spend_policy(
    *,
    criterion_ids: Sequence[str],
    pricing: PricingSnapshot,
    native_thin_budget_argument: str,
    executable_spec_sha256: str,
) -> SpendPolicy:
    """Build the per-arm, per-criterion policy for one minted spec."""

    ids = tuple(criterion_ids)
    if len(ids) != LAB_CRITERION_COUNT:
        raise Tier0MintError(
            f"pinned LAB task must contribute exactly {LAB_CRITERION_COUNT} "
            f"criterion IDs; got {len(ids)}"
        )
    if len(set(ids)) != len(ids):
        raise Tier0MintError("criterion IDs must be unique")
    judge_cap = judge_max_cost_usd(pricing)
    solver_arguments = {
        ARM_IDS[0]: CLAUDE_BUDGET_ARGUMENT,
        ARM_IDS[1]: native_thin_budget_argument,
    }
    solver_ceilings = tuple(
        SolverCeiling(
            arm_id=arm_id,
            provider=JUDGE_PROVIDER,
            model=REQUESTED_MODEL,
            max_cost_usd=SOLVER_MAX_COST_USD,
            max_requests=1,
            max_retries=0,
            max_parallelism=1,
            max_input_tokens=SOLVER_MAX_INPUT_TOKENS,
            max_output_tokens=SOLVER_MAX_OUTPUT_TOKENS,
            invocation_budget=InvocationBudget(
                mode="adapter_argument",
                argument_name=solver_arguments[arm_id],
                argument_value_usd=SOLVER_MAX_COST_USD,
            ),
        )
        for arm_id in ARM_IDS
    )
    judge_ceilings = tuple(
        JudgeCriterionCeiling(
            arm_id=arm_id,
            criterion_id=criterion_id,
            provider=JUDGE_PROVIDER,
            model=REQUESTED_MODEL,
            max_cost_usd=judge_cap,
            max_requests=JUDGE_MAX_ATTEMPTS,
            max_retries=JUDGE_MAX_ATTEMPTS - 1,
            max_parallelism=1,
            max_input_tokens=JUDGE_MAX_INPUT_TOKENS,
            max_output_tokens=JUDGE_MAX_OUTPUT_TOKENS,
            invocation_budget=InvocationBudget(mode="controller_reservation"),
        )
        # Ordinal order is load-bearing: the runner matches reservation N to
        # the Nth ceiling for its arm and rejects an identity mismatch.
        for arm_id in ARM_IDS
        for criterion_id in ids
    )
    return SpendPolicy(
        experiment_id=TIER0_EXPERIMENT_ID,
        executable_spec_sha256=executable_spec_sha256,
        pricing_snapshot_sha256=pricing.snapshot_sha256,
        experiment=ExperimentCeiling(
            max_cost_usd=experiment_max_cost_usd(pricing),
            max_requests=experiment_max_requests(),
            max_retries=experiment_max_requests() - 1,
            max_parallelism=1,
        ),
        solver_ceilings=solver_ceilings,
        judge_ceilings=judge_ceilings,
    )


def build_executable_spec(
    *,
    evaluator_wrapper_sha256: str,
    native_thin: NativeThinArmInput,
    pricing_snapshot_sha256: str,
    spend_policy_sha256: str,
) -> Tier0ExecutableSpec:
    """Build the frozen paired spec that the runner accepts only by hash."""

    return Tier0ExecutableSpec(
        experiment_id=TIER0_EXPERIMENT_ID,
        source_pin=SOURCE_PIN,
        evaluator_command=EVALUATOR_COMMAND_NAME,
        evaluator_wrapper_sha256=evaluator_wrapper_sha256,
        issuer_key_id=HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
        issuer_policy_sha256=harvey_lab_issuer_policy_sha256(),
        arms=(
            Tier0ArmSpec(
                arm_id=ARM_IDS[0],
                adapter="claude-code-clean-native",
                auth_profile="published-api-key",
                requested_model=REQUESTED_MODEL,
                solver_executable="claude",
                solver_executable_sha256=CLAUDE_EXECUTABLE_SHA256,
                solver_executable_version=CLAUDE_EXECUTABLE_VERSION,
                version_probe_args=("--version",),
                settings={"lab_task_id": PINNED_TASK_ID},
            ),
            Tier0ArmSpec(
                arm_id=ARM_IDS[1],
                adapter="harvey-lab",
                auth_profile="published-api-key",
                requested_model=REQUESTED_MODEL,
                solver_executable=native_thin.executable,
                solver_executable_sha256=native_thin.executable_sha256,
                solver_executable_version=native_thin.executable_version,
                version_probe_args=native_thin.version_probe_args,
                command=native_thin.command,
                settings={"lab_task_id": PINNED_TASK_ID},
            ),
        ),
        pricing_snapshot_sha256=pricing_snapshot_sha256,
        spend_policy_sha256=spend_policy_sha256,
    )


def mint_tier0_artifacts(
    output_dir: Path,
    *,
    criterion_ids: Sequence[str],
    native_thin: NativeThinArmInput,
    evaluator_wrapper_sha256: str | None = None,
    stem: str = "tier0-executable-spec",
) -> MintedTier0Artifacts:
    """Write the spec and its two deterministic sidecars into ``output_dir``.

    The two hash bindings are mutually referential by design, so they are
    written in the only order that closes: the policy digest excludes its own
    back-reference to the spec, so the spec can bind the policy, and the
    policy's back-reference is filled in afterwards without changing that
    digest. ``load_spend_artifacts`` re-checks both directions.
    """

    wrapper_digest = evaluator_wrapper_sha256 or wrapper_source_sha256()
    pricing = build_pricing_snapshot()
    provisional = build_spend_policy(
        criterion_ids=criterion_ids,
        pricing=pricing,
        native_thin_budget_argument=native_thin.budget_argument,
        executable_spec_sha256="sha256:" + "0" * 64,
    )
    spec = build_executable_spec(
        evaluator_wrapper_sha256=wrapper_digest,
        native_thin=native_thin,
        pricing_snapshot_sha256=pricing.snapshot_sha256,
        spend_policy_sha256=provisional.policy_sha256,
    )
    target = _require_output_dir(output_dir)
    spec_path = target / f"{stem}.json"
    pricing_path = target / f"{stem}.pricing-snapshot.json"
    policy_path = target / f"{stem}.spend-policy.json"
    # The runner hashes the file, so the digest must cover the exact bytes on
    # disk -- terminating newline included.
    spec_bytes = _canonical_bytes(spec.to_record()) + b"\n"
    _write_new(spec_path, spec_bytes)
    spec_sha256 = "sha256:" + sha256(spec_bytes).hexdigest()
    final = build_spend_policy(
        criterion_ids=criterion_ids,
        pricing=pricing,
        native_thin_budget_argument=native_thin.budget_argument,
        executable_spec_sha256=spec_sha256,
    )
    if final.policy_sha256 != provisional.policy_sha256:
        raise Tier0MintError(
            "spend policy digest changed when its spec back-reference was set"
        )
    _write_new(pricing_path, _canonical_bytes(pricing.to_record()) + b"\n")
    _write_new(policy_path, _canonical_bytes(final.to_record()) + b"\n")
    # Prove the artifacts satisfy the same pre-credential validation the
    # runner performs, so a mint can never emit a policy that only fails later.
    final.validate_before_credentials(pricing)
    return MintedTier0Artifacts(
        spec_path=spec_path,
        pricing_path=pricing_path,
        policy_path=policy_path,
        spec_sha256=spec_sha256,
        pricing_snapshot_sha256=pricing.snapshot_sha256,
        spend_policy_sha256=final.policy_sha256,
    )


def criterion_ids_from_private_task(path: Path) -> tuple[str, ...]:
    """Read the pinned criterion IDs, in upstream order, from private material.

    The file is hash-verified against the frozen ``task.json`` digest before it
    is parsed, so a mint cannot silently bind ceilings to a different task.
    """

    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise Tier0MintError("private task material is unreadable") from exc
    observed = sha256(payload).hexdigest()
    if observed != PINNED_TASK_SHA256:
        raise Tier0MintError(
            "private task material does not match the pinned task.json digest"
        )
    try:
        record = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Tier0MintError("private task material is not valid JSON") from exc
    if not isinstance(record, dict):
        raise Tier0MintError("private task material must be an object")
    criteria = cast(Mapping[str, Any], record).get("criteria")
    if not isinstance(criteria, list):
        raise Tier0MintError("private task material has no criteria array")
    ids: list[str] = []
    for ordinal, criterion in enumerate(cast(list[Any], criteria), start=1):
        if not isinstance(criterion, dict):
            raise Tier0MintError(f"criterion {ordinal} is not an object")
        value = cast(Mapping[str, Any], criterion).get("id")
        if not isinstance(value, str) or not value.strip():
            raise Tier0MintError(f"criterion {ordinal} has no usable id")
        ids.append(value)
    return tuple(ids)


def _require_output_dir(output_dir: Path) -> Path:
    if output_dir.is_symlink():
        raise Tier0MintError("mint output directory must not be a symlink")
    if not output_dir.is_dir():
        raise Tier0MintError("mint output directory must exist")
    return output_dir.resolve()


def _write_new(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise Tier0MintError(f"refusing to overwrite {path.name}") from exc
    except OSError as exc:
        raise Tier0MintError(f"could not write {path.name}") from exc


def _canonical_bytes(record: Mapping[str, Any]) -> bytes:
    return json.dumps(
        record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
