"""Estimated Jev token admission, separate from summary length targets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import cast

import tiktoken

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1

JEV_TOTAL_TOKEN_LIMIT = 64_000
JEV_STATE_QUESTION_TOKEN_LIMIT = 32_000


@lru_cache(maxsize=1)
def _encodings() -> tuple[tiktoken.Encoding, ...]:
    return tuple(tiktoken.get_encoding(name) for name in ("cl100k_base", "o200k_base"))


def _proxy_tokens(value: object) -> int:
    text = ARTIFACT_CANONICAL_JSON_V1.encode(value).decode("utf-8")
    return max(
        len(encoding.encode(text, disallowed_special=())) for encoding in _encodings()
    )


def _with_headroom(tokens: int) -> int:
    # Jev has no published tokenizer. Across the 91 completed Luna-summary
    # cases, reported input usage was at most 1.180 times the larger proxy.
    # Use 1.5 times plus 1,024 formatting tokens; this remains an estimate,
    # not a guarantee about Jev's tokenizer or a substitute for provider errors.
    return (tokens * 3 + 1) // 2 + 1024


@dataclass(frozen=True)
class JevContextEstimate:
    """Token estimates including headroom for both documented Jev limits."""

    total_tokens: int
    state_plus_longest_question_tokens: int

    @property
    def fits(self) -> bool:
        """Whether both estimates fit the documented token budgets."""

        return (
            self.total_tokens <= JEV_TOTAL_TOKEN_LIMIT
            and self.state_plus_longest_question_tokens
            <= JEV_STATE_QUESTION_TOKEN_LIMIT
        )


def estimate_request_context(request: Mapping[str, object]) -> JevContextEstimate:
    """Estimate with two proxy tokenizers; neither is Jev's official tokenizer."""

    questions = request.get("questions")
    if not isinstance(questions, Mapping) or not questions or "state" not in request:
        raise ValueError("Jev context sizing requires a state and nonempty questions")
    question_tokens = max(
        _proxy_tokens({key: value})
        for key, value in cast(Mapping[str, object], questions).items()
    )
    return JevContextEstimate(
        total_tokens=_with_headroom(_proxy_tokens(dict(request))),
        state_plus_longest_question_tokens=_with_headroom(
            _proxy_tokens(request["state"]) + question_tokens
        ),
    )
