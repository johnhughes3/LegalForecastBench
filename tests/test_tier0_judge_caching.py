"""The Tier-0 judge sends each arm's deliverable once at full price.

Every criterion of an arm is judged against the same deliverable, so the
deliverable leads the user turn behind a cache breakpoint and the criterion
follows it. These tests pin the two halves of that: the prompt split, and a
ledger that still counts cached input rather than treating it as free.
"""

from __future__ import annotations

from hashlib import sha256

from legalforecast.multiharness.harvey_lab_evaluator import HarveyLabJudgeRequest
from legalforecast.multiharness.harvey_lab_production_runner import (
    JudgeDeliverable,
    ProductionJudgeCall,
)
from legalforecast.multiharness.tier0_mint import build_pricing_snapshot
from legalforecast.multiharness.tier0_production_factory import (
    AnthropicMessagesJudgeAdapter,
    JudgeTransportResult,
)


class _SplitTransport:
    """A fake provider that keeps the cached prefix and the criterion apart."""

    def __init__(self, *, cache_read: int = 0, cache_write: int = 0) -> None:
        self.cache_read = cache_read
        self.cache_write = cache_write
        self.prefixes: list[str] = []
        self.suffixes: list[str] = []

    def __call__(
        self,
        *,
        api_key: str,
        model: str,
        system: str,
        cached_prefix: str,
        prompt: str,
        max_output_tokens: int,
    ) -> JudgeTransportResult:
        del api_key, system, max_output_tokens
        self.prefixes.append(cached_prefix)
        self.suffixes.append(prompt)
        return JudgeTransportResult(
            verdict_text="pass",
            resolved_model=model,
            input_tokens=1200,
            output_tokens=1,
            raw_response=b'{"stub":true}',
            cache_read_input_tokens=self.cache_read,
            cache_creation_input_tokens=self.cache_write,
        )


def _adapter(transport: _SplitTransport) -> AnthropicMessagesJudgeAdapter:
    return AnthropicMessagesJudgeAdapter(
        pricing_snapshot=build_pricing_snapshot(),
        secret_loader=lambda _e, _p, _n: "stub-key",
        transport=transport,
        max_prompt_bytes=100_000,
    )


def _call(criterion_id: str, deliverable_text: str) -> ProductionJudgeCall:
    return ProductionJudgeCall(
        request=HarveyLabJudgeRequest(
            ordinal=1, criterion_id=criterion_id, attempt_index=0
        ),
        run_spec=None,  # type: ignore[arg-type]
        criterion={"id": criterion_id, "title": "t", "match_criteria": "requirement"},
        deliverable=JudgeDeliverable(
            artifact_paths=("memo.docx",),
            text=deliverable_text,
            sha256="sha256:" + sha256(deliverable_text.encode()).hexdigest(),
        ),
    )


def test_judge_settles_cached_input_never_below_its_cost() -> None:
    """Anthropic's ``input_tokens`` is the uncached remainder only.

    Settling on it alone would make every cache read free in the ledger.
    Reads settle at the full input rate (billed 0.1x) and writes at their
    billed 1.25x, rounded up, so no call settles below what it cost.
    """

    response = _adapter(_SplitTransport(cache_read=9000, cache_write=300))(
        _call("criterion-01", "The memo identifies the tolling issue.")
    )
    assert response.usage.input_tokens == 1200 + 9000 + 375


def test_the_deliverable_is_a_criterion_independent_prefix() -> None:
    transport = _SplitTransport()
    adapter = _adapter(transport)
    adapter(_call("criterion-01", "The memo identifies the tolling issue."))
    adapter(_call("criterion-02", "The memo identifies the tolling issue."))
    assert transport.prefixes[0] == transport.prefixes[1]
    assert "The memo identifies the tolling issue." in transport.prefixes[0]
    assert "requirement" not in transport.prefixes[0]
    assert "requirement" in transport.suffixes[0]


def test_a_write_that_does_not_divide_by_four_rounds_up() -> None:
    response = _adapter(_SplitTransport(cache_write=1025))(
        _call("criterion-01", "The memo identifies the tolling issue.")
    )
    assert response.usage.input_tokens == 1200 + 1282
