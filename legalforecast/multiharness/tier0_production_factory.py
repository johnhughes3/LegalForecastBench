"""The supported production evaluator/provider factory for paid Tier-0.

``legalforecast.multiharness.cli`` refuses paid Tier-0 execution unless a
reviewed production evaluator factory has been installed.  Until this module
existed nothing in the supported tree installed one, so the refusal was
unreachable-by-construction rather than fail-closed-by-design: an operator
following the documented command could never get past it, and the only way
forward was an unreviewed embedding runtime.  This module is that missing
half -- enforcement now ships with its issuance.

Three properties are deliberate:

* **No selector.**  There is exactly one supported production adapter and it is
  installed unconditionally.  An adapter chosen by flag or environment variable
  would be a run-varying input that the frozen spec hash does not cover, which
  is precisely what the executable freeze forbids.
* **No credential discovery.**  The judge API key is fetched through the
  sanctioned Infisical wrapper by an injected callback, at the moment a paid
  call is made, and never from the host environment.  This mirrors the
  evaluator-issuer signer seam exactly.
* **No fixture reachability.**  Fixture identities are refused by
  ``ProductionJudgeResponse``; this module never constructs one, and the
  provider transport is required rather than defaulted to a stub.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.multiharness.auth_profiles import AuthProfileError
from legalforecast.multiharness.harvey_lab_production_runner import (
    JudgeDeliverable,
    ProductionEvaluatorRunnerError,
    ProductionHarveyLabEvaluatorRunner,
    ProductionJudgeCall,
    ProductionJudgeResponse,
)
from legalforecast.multiharness.local_cli_environment import (
    fetch_named_infisical_secret,
)
from legalforecast.multiharness.spend import (
    PricingSnapshot,
    SpendPolicy,
    UsageObservation,
)
from legalforecast.multiharness.tier0_evaluator_wrapper import wrapper_source_sha256
from legalforecast.multiharness.tier0_runner import (
    Tier0EvaluatorConfiguration,
    Tier0EvaluatorProvenanceFactory,
    Tier0EvaluatorProvenanceProvider,
    Tier0ExecutableSpec,
)

# The judge credential is a distinct secret from the evaluator signing seed and
# lives at its own stage path. A name/path/environment mismatch is refused
# before any fetch, so a misconfigured caller cannot widen the namespace.
JUDGE_CREDENTIAL_INFISICAL_ENVIRONMENT = "dev"
JUDGE_CREDENTIAL_INFISICAL_PATH = (
    "/agents/sandbox/legalforecastbench/harness-runtime/tier0-judge"
)
JUDGE_CREDENTIAL_NAME = "TIER0_JUDGE_ANTHROPIC_API_KEY"

JUDGE_PROVIDER = "anthropic"
# Pinned by the structural freeze. The adapter refuses a resolved identity that
# differs from what the spec requested, so this is an assertion, not a default.
JUDGE_REQUESTED_MODEL = "claude-sonnet-4-6"
# The paid path fails closed rather than silently running against an SDK whose
# request shape was never characterized for this freeze.
REQUIRED_ANTHROPIC_SDK_VERSION = "0.116.0"

# Tokens reserved for provider-side message framing, which the prompt bytes do
# not account for. Small and fixed: the bound below only has to be safe, and
# framing overhead does not scale with the deliverable.
JUDGE_PROMPT_FRAMING_TOKEN_RESERVE = 256

_PASS = "pass"
_FAIL = "fail"

JUDGE_SETTINGS: Mapping[str, object] = {
    "model": JUDGE_REQUESTED_MODEL,
    "provider_sampling_policy": "provider_default",
    "max_output_tokens": 16,
    "tools": [],
    "stop_sequences": [],
    "anthropic_sdk_version": REQUIRED_ANTHROPIC_SDK_VERSION,
}
JUDGE_SYSTEM_PROMPT = (
    "You are grading one binary criterion for a legal drafting task. "
    "Read the criterion and the candidate deliverable text. "
    "Reply with exactly one lowercase word and nothing else: "
    "pass if the deliverable satisfies the criterion, fail otherwise."
)
JUDGE_OUTPUT_SCHEMA: Mapping[str, object] = {
    "type": "string",
    "enum": [_PASS, _FAIL],
    "description": "The only accepted verdicts for one Harvey LAB criterion.",
}
RUNTIME_POLICY: Mapping[str, object] = {
    "provider": JUDGE_PROVIDER,
    "surface": "messages",
    "sdk": "anthropic",
    "sdk_version": REQUIRED_ANTHROPIC_SDK_VERSION,
    "credential_backend": "infisical-agent-sandbox",
    "credential_environment": JUDGE_CREDENTIAL_INFISICAL_ENVIRONMENT,
    "credential_path": JUDGE_CREDENTIAL_INFISICAL_PATH,
    "credential_name": JUDGE_CREDENTIAL_NAME,
    "host_environment_fallback": False,
}
EGRESS_POLICY: Mapping[str, object] = {
    "allowed_hosts": ["api.anthropic.com"],
    "solver_egress": "denied",
    "evaluator_egress": "judge_provider_only",
}
RESOURCE_POLICY: Mapping[str, object] = {
    "judge_calls_per_arm": 23,
    "max_attempts_per_criterion": 3,
    "parallelism": 1,
}
TOKEN_ACCOUNTING_POLICY: Mapping[str, object] = {
    "source": "provider_usage",
    "required_fields": ["input_tokens", "output_tokens"],
    "subscription_usage": "refused",
    "unknown_cost": "refused",
}


class ProductionFactoryError(ValueError):
    """The supported production evaluator seam could not be constructed."""


class JudgeTransport(Protocol):
    """One provider request/response round trip for a single criterion."""

    def __call__(
        self,
        *,
        api_key: str,
        model: str,
        system: str,
        prompt: str,
        max_output_tokens: int,
    ) -> JudgeTransportResult:
        """Issue the request and report what the provider actually returned."""
        ...


@dataclass(frozen=True, slots=True)
class JudgeTransportResult:
    """What a transport must report for a settlement to be auditable."""

    verdict_text: str
    resolved_model: str
    input_tokens: int
    output_tokens: int
    raw_response: bytes


def infisical_tier0_judge_secret_loader(environment: str, path: str, name: str) -> str:
    """Load the judge API key only through the sanctioned Infisical wrapper.

    Refuses before fetching when the coordinates are not the approved ones, so
    a caller cannot use this loader to read an arbitrary secret.
    """

    if environment != JUDGE_CREDENTIAL_INFISICAL_ENVIRONMENT:
        raise ProductionFactoryError("Tier-0 judge credential must use Infisical dev")
    if path != JUDGE_CREDENTIAL_INFISICAL_PATH:
        raise ProductionFactoryError(
            "Tier-0 judge credential path is outside the sanctioned namespace"
        )
    if name != JUDGE_CREDENTIAL_NAME:
        raise ProductionFactoryError("Tier-0 judge credential name is not approved")
    try:
        return fetch_named_infisical_secret(
            environment=environment, path=path, name=name
        )
    except AuthProfileError as exc:
        raise ProductionFactoryError(
            "Tier-0 judge credential is unavailable from the Infisical wrapper"
        ) from exc


def anthropic_messages_transport(
    *,
    api_key: str,
    model: str,
    system: str,
    prompt: str,
    max_output_tokens: int,
) -> JudgeTransportResult:
    """Issue one judge request through the official Anthropic SDK.

    Imported lazily so that neither this module nor the provider-free tests
    require the optional ``tier0-judge-adapter`` extra to be installed.
    """

    try:
        # Imported by name rather than by statement: the SDK is an optional
        # extra, so a static import would make this module unanalyzable
        # wherever the extra is not installed.
        sdk: Any = import_module("anthropic")
    except ImportError as exc:  # pragma: no cover - exercised by the refusal test
        raise ProductionFactoryError(
            "the Anthropic SDK is not installed; install the "
            "tier0-judge-adapter extra before a paid Tier-0 run"
        ) from exc
    observed_version = str(getattr(sdk, "__version__", ""))
    if observed_version != REQUIRED_ANTHROPIC_SDK_VERSION:
        raise ProductionFactoryError(
            "installed Anthropic SDK version does not match the frozen "
            "judge runtime policy"
        )
    client: Any = sdk.Anthropic(api_key=api_key)
    response: Any = client.messages.create(
        model=model,
        max_tokens=max_output_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(
        str(block.text)
        for block in cast(list[Any], response.content)
        if str(getattr(block, "type", "")) == "text"
    )
    return JudgeTransportResult(
        verdict_text=text,
        resolved_model=str(response.model),
        input_tokens=int(response.usage.input_tokens),
        output_tokens=int(response.usage.output_tokens),
        raw_response=str(response.to_json()).encode("utf-8"),
    )


@dataclass(frozen=True, slots=True)
class AnthropicMessagesJudgeAdapter:
    """One reviewed provider call per criterion, with allocable accounting."""

    pricing_snapshot: PricingSnapshot
    secret_loader: Callable[[str, str, str], str]
    transport: JudgeTransport
    max_prompt_bytes: int
    requested_model: str = JUDGE_REQUESTED_MODEL

    def __call__(self, call: ProductionJudgeCall) -> ProductionJudgeResponse:
        criterion = call.criterion
        prompt = _judge_prompt(criterion, call.deliverable)
        # A token spans at least one byte, so bounding the prompt's bytes
        # bounds its tokens. Refusing an oversized prompt is deliberate: a
        # truncated deliverable would produce a confident verdict on a
        # document the candidate did not write, and silently overrun the
        # per-call ceiling the spend policy reserved for this request.
        prompt_bytes = len(JUDGE_SYSTEM_PROMPT.encode("utf-8")) + len(
            prompt.encode("utf-8")
        )
        if prompt_bytes > self.max_prompt_bytes:
            raise ProductionFactoryError(
                "judge prompt exceeds the input budget the spend policy reserved"
            )
        api_key = self.secret_loader(
            JUDGE_CREDENTIAL_INFISICAL_ENVIRONMENT,
            JUDGE_CREDENTIAL_INFISICAL_PATH,
            JUDGE_CREDENTIAL_NAME,
        )
        if not api_key.strip():
            raise ProductionFactoryError("Tier-0 judge credential is empty")
        result = self.transport(
            api_key=api_key,
            model=self.requested_model,
            system=JUDGE_SYSTEM_PROMPT,
            prompt=prompt,
            max_output_tokens=cast(int, JUDGE_SETTINGS["max_output_tokens"]),
        )
        if type(result) is not JudgeTransportResult:
            raise ProductionFactoryError("judge transport returned an invalid result")
        usage = UsageObservation(
            basis="estimated_from_pricing_snapshot",
            pricing_snapshot_sha256=self.pricing_snapshot.snapshot_sha256,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        verdict = result.verdict_text.strip().lower()
        if verdict not in {_PASS, _FAIL}:
            # An unparseable verdict is retryable, not a silent failure: the
            # request was billed, so it must still settle against the ceiling.
            return ProductionJudgeResponse(
                verdict=None,
                judge_resolved_identity=result.resolved_model,
                usage=usage,
                raw_response=result.raw_response,
                retryable=True,
            )
        return ProductionJudgeResponse(
            verdict=verdict,
            judge_resolved_identity=result.resolved_model,
            usage=usage,
            raw_response=result.raw_response,
        )


def build_production_evaluator(
    spec: Tier0ExecutableSpec,
    spec_path: Path,
    private_root: Path,
    policy: SpendPolicy,
    pricing: PricingSnapshot,
    *,
    secret_loader: Callable[[str, str, str], str] | None = None,
    transport: JudgeTransport | None = None,
) -> tuple[ProductionHarveyLabEvaluatorRunner, Tier0EvaluatorProvenanceProvider]:
    """Build the reviewed paid evaluator seam for one Tier-0 spec."""

    del spec_path  # Retention is rooted in the caller-supplied private root.
    if pricing.snapshot_sha256 != policy.pricing_snapshot_sha256:
        raise ProductionFactoryError("pricing snapshot does not match the spend policy")
    try:
        pricing.rate_for(JUDGE_PROVIDER, JUDGE_REQUESTED_MODEL)
    except Exception as exc:
        raise ProductionFactoryError(
            "pricing snapshot has no auditable rate for the pinned judge model"
        ) from exc
    adapter = AnthropicMessagesJudgeAdapter(
        pricing_snapshot=pricing,
        secret_loader=secret_loader or infisical_tier0_judge_secret_loader,
        transport=transport or anthropic_messages_transport,
        max_prompt_bytes=judge_max_prompt_bytes(policy),
    )
    writer = JudgeAttemptWriter(private_root / "evaluator" / "judge-attempts")
    # The receipt must attest the wrapper the run is pinned to, which preflight
    # verified against the installed bytes -- not whatever the repo checkout
    # happens to hold at construction time.
    installed_wrapper_sha256 = wrapper_source_sha256()
    if installed_wrapper_sha256 != spec.evaluator_wrapper_sha256:
        raise ProductionFactoryError(
            "evaluator wrapper source does not match the digest pinned by the spec"
        )
    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=adapter,
        attempt_writer=writer,
        pricing_snapshot=pricing,
        pricing_provider=JUDGE_PROVIDER,
        pricing_model=JUDGE_REQUESTED_MODEL,
        max_attempts=cast(int, RESOURCE_POLICY["max_attempts_per_criterion"]),
        # Pinned, not defaulted: pricing_model below costs every call at the
        # frozen Sonnet 4.6 rate, so a substituted model must refuse rather
        # than be accepted and billed against a rate it never earned.
        expected_judge_identity=JUDGE_REQUESTED_MODEL,
        evaluator_executable_version=(
            f"harvey-lab-eval@{spec.evaluator_wrapper_sha256}"
        ),
    )
    provenance = Tier0EvaluatorProvenanceFactory(
        configuration=production_evaluator_configuration(spec, pricing)
    )
    return runner, provenance


def judge_max_prompt_bytes(policy: SpendPolicy) -> int:
    """Return the prompt byte budget implied by the minted judge ceilings.

    The bound is taken from the spend policy rather than a module constant so
    it is covered by the executable spec hash: the same artifact that reserves
    a per-call input allowance is the one that decides how much deliverable
    text may be sent under it. Bytes are a safe proxy for tokens because a
    token always spans at least one byte.
    """

    ceilings = policy.judge_ceilings
    if not ceilings:
        raise ProductionFactoryError("spend policy declares no judge ceilings")
    budget = min(ceiling.max_input_tokens for ceiling in ceilings)
    allowance = budget - JUDGE_PROMPT_FRAMING_TOKEN_RESERVE
    if allowance <= 0:
        raise ProductionFactoryError("judge input ceiling leaves no room for a prompt")
    return allowance


def production_evaluator_configuration(
    spec: Tier0ExecutableSpec,
    pricing: PricingSnapshot,
) -> Tier0EvaluatorConfiguration:
    """Return the immutable evaluator identity bound into every receipt."""

    return Tier0EvaluatorConfiguration(
        evaluator_repository=spec.source_pin.repository,
        evaluator_commit=spec.source_pin.commit,
        evaluator_tree=spec.source_pin.tree,
        evaluator_file_manifest_sha256=spec.evaluator_wrapper_sha256,
        evaluator_image_digest=spec.evaluator_wrapper_sha256,
        judge_requested_identity=f"{JUDGE_PROVIDER}:{JUDGE_REQUESTED_MODEL}",
        judge_settings_sha256=policy_digest(JUDGE_SETTINGS),
        judge_prompt_sha256=text_digest(JUDGE_SYSTEM_PROMPT),
        judge_output_schema_sha256=policy_digest(JUDGE_OUTPUT_SCHEMA),
        runtime_policy_sha256=policy_digest(RUNTIME_POLICY),
        egress_policy_sha256=policy_digest(EGRESS_POLICY),
        resource_policy_sha256=policy_digest(RESOURCE_POLICY),
        token_accounting_policy_sha256=policy_digest(TOKEN_ACCOUNTING_POLICY),
        cost_basis="estimated_from_pricing_snapshot",
        pricing_snapshot_sha256=pricing.snapshot_sha256,
        is_fixture=False,
    )


def install_supported_production_factory() -> None:
    """Install the single supported production factory on the CLI seam."""

    from legalforecast.multiharness import cli as multiharness_cli

    multiharness_cli.install_tier0_production_evaluator_factory(
        build_production_evaluator
    )


@dataclass(frozen=True, slots=True)
class JudgeAttemptWriter:
    """Retain every billed judge attempt, including retries, before settlement."""

    root: Path

    def __call__(
        self, call: ProductionJudgeCall, response: ProductionJudgeResponse
    ) -> None:
        directory = self.root / call.request.criterion_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"attempt-{call.request.attempt_index}.json"
        record = {
            "criterion_id": call.request.criterion_id,
            "ordinal": call.request.ordinal,
            "attempt_index": call.request.attempt_index,
            # Names the exact deliverable bytes this verdict was formed
            # against, so a retained attempt is auditable on its own.
            "deliverable_sha256": call.deliverable.sha256,
            "verdict": response.verdict,
            "judge_resolved_identity": response.judge_resolved_identity,
            "retryable": response.retryable,
            "usage": {
                "basis": response.usage.basis,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "pricing_snapshot_sha256": response.usage.pricing_snapshot_sha256,
            },
            "raw_response_sha256": "sha256:"
            + sha256(response.raw_response).hexdigest(),
        }
        payload = _canonical_bytes(record)
        # Exclusive create: an attempt file must never be silently rewritten,
        # or a retry could erase the evidence of the attempt it replaced.
        try:
            with target.open("xb") as handle:
                handle.write(payload + b"\n")
        except OSError as exc:
            raise ProductionEvaluatorRunnerError(
                "judge attempt retention failed; refusing to continue"
            ) from exc
        raw_target = directory / f"attempt-{call.request.attempt_index}.raw"
        try:
            with raw_target.open("xb") as handle:
                handle.write(response.raw_response)
        except OSError as exc:
            raise ProductionEvaluatorRunnerError(
                "judge raw-response retention failed; refusing to continue"
            ) from exc


def _judge_prompt(
    criterion: Mapping[str, object], deliverable: JudgeDeliverable
) -> str:
    """Render the per-criterion prompt from private task material and the work.

    Including the deliverable is the point of the request: a criterion alone
    tells the judge what to look for but never what to look at, and a judge
    given only the criterion still answers -- confidently, billably, and
    identically for every candidate.
    """

    title = criterion.get("title")
    match_criteria = criterion.get("match_criteria")
    if not isinstance(match_criteria, str) or not match_criteria.strip():
        raise ProductionFactoryError("criterion is missing its private match text")
    if type(deliverable) is not JudgeDeliverable:
        raise ProductionFactoryError("judge call is missing its candidate deliverable")
    heading = title if isinstance(title, str) and title.strip() else "criterion"
    return (
        f"Criterion: {heading}\n\n"
        f"Requirement:\n{match_criteria}\n\n"
        f"Candidate deliverable ({deliverable.basename}):\n"
        f"<deliverable>\n{deliverable.text}\n</deliverable>\n"
    )


def policy_digest(record: Mapping[str, object]) -> str:
    """Return the canonical digest of a frozen policy record."""

    return "sha256:" + sha256(_canonical_bytes(record)).hexdigest()


def text_digest(value: str) -> str:
    """Return the digest of frozen prompt text."""

    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


def _canonical_bytes(record: Mapping[str, Any]) -> bytes:
    return json.dumps(
        record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def judge_worst_case_microusd(
    pricing: PricingSnapshot,
    *,
    max_input_tokens: int,
    max_output_tokens: int,
) -> int:
    """Return the worst-case cost of one judge call under this snapshot."""

    rate = pricing.rate_for(JUDGE_PROVIDER, JUDGE_REQUESTED_MODEL)
    return rate.worst_case_microusd(
        input_tokens=max_input_tokens, output_tokens=max_output_tokens
    )


def microusd_to_usd(value: int) -> str:
    """Render a micro-USD integer as a canonical USD decimal string."""

    return format(Decimal(value) / Decimal(1_000_000), "f")
