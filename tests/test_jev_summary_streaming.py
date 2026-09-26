"""Exercise the managed Responses stream through cache and spend settlement."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal

import httpx2
import legalforecast.jev.prepare as prepare
import pytest
from legalforecast.evals.model_registry import ModelRegistryEntry
from openai import AsyncOpenAI as RealAsyncOpenAI
from tests.test_jev_grok_prepare import (
    _documents,  # pyright: ignore[reportPrivateUsage]
    _execution,  # pyright: ignore[reportPrivateUsage]
)
from tests.test_jev_grok_prepare import (
    _entry as _grok_entry,  # pyright: ignore[reportPrivateUsage]
)
from tests.test_jev_prepare import (
    _entry as _luna_entry,  # pyright: ignore[reportPrivateUsage]
)

_StreamEnd = Literal["completed", "eof", "read_error", "incomplete", "missing_usage"]
_TEXT_PARTS = ("First substantive argument. ", "Final substantive argument.")


def _event(kind: str, sequence: int, **payload: object) -> bytes:
    return (
        f"event: {kind}\ndata: "
        + json.dumps({"type": kind, "sequence_number": sequence, **payload})
        + "\n\n"
    ).encode()


def _response(status: str, model: str) -> dict[str, object]:
    return {
        "id": "resp_fixture",
        "object": "response",
        "created_at": 1_800_000_000,
        "model": model,
        "status": status,
        "output": [],
        "error": None,
        "incomplete_details": None,
    }


class _SummaryStream(httpx2.AsyncByteStream):
    def __init__(self, ending: _StreamEnd, model: str) -> None:
        self.ending = ending
        self.model = model

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield _event(
            "response.created", 0, response=_response("in_progress", self.model)
        )
        for sequence, text in enumerate(_TEXT_PARTS, start=1):
            yield _event(
                "response.output_text.delta",
                sequence,
                item_id="msg_fixture",
                output_index=0,
                content_index=0,
                delta=text,
                logprobs=[],
            )
        if self.ending == "read_error":
            raise httpx2.ReadError("fixture disconnect after partial text")
        if self.ending == "eof":
            return
        status = "incomplete" if self.ending == "incomplete" else "completed"
        response = _response(status, self.model)
        if self.ending != "missing_usage":
            response["usage"] = {
                "input_tokens": 123,
                "output_tokens": 45,
                "total_tokens": 168,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 10},
            }
        if status == "incomplete":
            response["incomplete_details"] = {"reason": "max_output_tokens"}
        yield _event(f"response.{status}", 3, response=response)


def _install_transport(
    monkeypatch: pytest.MonkeyPatch, ending: _StreamEnd
) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        requests.append(body)
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_SummaryStream(ending, body["model"]),
        )

    def client(
        *, api_key: str, max_retries: int, base_url: str | None = None
    ) -> RealAsyncOpenAI:
        assert max_retries == 0
        return RealAsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handle)),
        )

    monkeypatch.setenv("AI_GATEWAY_API_KEY", "fixture-key")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    monkeypatch.setattr(prepare, "AsyncOpenAI", client)
    return requests


@pytest.mark.parametrize("entry", [_grok_entry(), _luna_entry()], ids=["grok", "luna"])
def test_completed_stream_preserves_all_text_usage_and_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: ModelRegistryEntry
) -> None:
    execution = _execution(tmp_path)
    requests = _install_transport(monkeypatch, "completed")
    cache_path = tmp_path / "summaries.json"
    ledger_path = tmp_path / "ledger.sqlite3"

    def run() -> dict[str, int]:
        return prepare.prepare_summaries(
            execution,
            entry=entry,
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=20_000_000,
            summary_profile="short",
        )

    result = run()
    count = len(_documents(execution))
    assert result["created"] == count
    assert len(requests) == count
    for request in requests:
        assert request["stream"] is True
        assert not request.get("tools")
        reasoning = request["reasoning"]
        assert isinstance(reasoning, dict)
        assert reasoning["effort"] == "high"
    saved = json.loads(cache_path.read_text())["records"]
    summaries = [
        summary for documents in saved.values() for summary in documents.values()
    ]
    assert len(summaries) == count
    for summary in summaries:
        assert summary["text"] == "".join(_TEXT_PARTS)
        assert summary["input_tokens"] == 123
        assert summary["output_tokens"] == 45
        expected_cost = (
            123 * entry.input_token_price + 45 * entry.output_token_price
        ) / 1_000_000
        assert summary["estimated_cost_usd"] == pytest.approx(expected_cost)
    with sqlite3.connect(ledger_path) as connection:
        rows = connection.execute(
            "SELECT status, actual_microusd FROM provider_attempts"
        ).fetchall()
    expected_microusd = round(
        123 * entry.input_token_price + 45 * entry.output_token_price
    )
    assert rows == [("settled", expected_microusd)] * count
    reused = run()
    assert reused["created"] == 0
    assert reused["reused"] == count
    assert len(requests) == count


@pytest.mark.parametrize("ending", ["eof", "read_error", "incomplete", "missing_usage"])
def test_failed_stream_never_caches_partial_text_or_releases_charge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ending: _StreamEnd
) -> None:
    execution = _execution(tmp_path)
    requests = _install_transport(monkeypatch, ending)
    cache_path = tmp_path / "summaries.json"
    ledger_path = tmp_path / "ledger.sqlite3"
    expected = httpx2.ReadError if ending == "read_error" else ValueError
    with pytest.raises(expected):
        prepare.prepare_summaries(
            execution,
            entry=_grok_entry(),
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=20_000_000,
            summary_profile="short",
        )
    assert len(requests) == 1
    assert requests[0]["stream"] is True
    assert not cache_path.exists() or not json.loads(cache_path.read_text())["records"]
    with sqlite3.connect(ledger_path) as connection:
        rows = connection.execute(
            "SELECT status, actual_microusd, reservation_microusd "
            "FROM provider_attempts"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "ambiguous"
    assert rows[0][1] is None
    assert rows[0][2] > 0
